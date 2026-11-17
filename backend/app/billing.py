import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.audit import record_event
from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import BillingInvoice, BillingSubscription, ProcessedBillingWebhook, User

router = APIRouter(prefix='/billing', tags=['billing'])

def _stripe_ready(settings):
    if not settings.stripe_secret_key or not settings.stripe_price_id:
        raise HTTPException(status_code=503, detail='Billing is not configured by the panel administrator')
    return settings

@router.post('/checkout')
def create_checkout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = _stripe_ready(get_settings())
    existing = db.scalar(select(BillingSubscription).where(BillingSubscription.user_id == user.id))
    if existing and existing.status in ('active','trialing','past_due','unpaid'):
        raise HTTPException(status_code=409, detail='An existing subscription is already attached to this account')
    form = {
        'mode':'subscription',
        'line_items[0][price]':settings.stripe_price_id,
        'line_items[0][quantity]':'1',
        'client_reference_id':str(user.id),
        'customer_email':user.email,
        'metadata[user_id]':str(user.id),
        'subscription_data[metadata][user_id]':str(user.id),
        'success_url':settings.frontend_url.rstrip('/')+'/?billing=success',
        'cancel_url':settings.frontend_url.rstrip('/')+'/?billing=cancelled',
    }
    if existing and existing.stripe_customer_id:
        form.pop('customer_email',None)
        form['customer']=existing.stripe_customer_id
    try:
        response=httpx.post('https://api.stripe.com/v1/checkout/sessions',data=form,
            auth=(settings.stripe_secret_key,''),timeout=12.0,
            headers={'Idempotency-Key':f'lighting-checkout-{user.id}-{int(time.time()//30)}'})
        response.raise_for_status()
        checkout=response.json()
    except (httpx.HTTPError,ValueError):
        raise HTTPException(status_code=502,detail='Payment provider could not create a checkout session')
    if not checkout.get('url','').startswith('https://checkout.stripe.com/'):
        raise HTTPException(status_code=502,detail='Payment provider returned an invalid checkout URL')
    record_event(db,'billing.checkout.created',user,'Stripe Checkout session created')
    db.commit()
    return {'checkout_url':checkout['url']}

@router.post('/portal')
def create_portal(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings=_stripe_ready(get_settings())
    subscription=db.scalar(select(BillingSubscription).where(BillingSubscription.user_id==user.id))
    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(status_code=404,detail='No payment customer is linked to this account yet')
    try:
        response=httpx.post('https://api.stripe.com/v1/billing_portal/sessions',
            data={'customer':subscription.stripe_customer_id,'return_url':settings.frontend_url.rstrip('/')+'/?billing=return'},
            auth=(settings.stripe_secret_key,''),timeout=12.0)
        response.raise_for_status()
        portal=response.json()
    except (httpx.HTTPError,ValueError):
        raise HTTPException(status_code=502,detail='Payment provider could not create a billing portal session')
    if not portal.get('url','').startswith('https://billing.stripe.com/'):
        raise HTTPException(status_code=502,detail='Payment provider returned an invalid billing portal URL')
    return {'portal_url':portal['url']}

@router.get('/me')
def billing_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subscription=db.scalar(select(BillingSubscription).where(BillingSubscription.user_id==user.id))
    invoices=db.scalars(select(BillingInvoice).where(BillingInvoice.user_id==user.id).order_by(BillingInvoice.created_at.desc()).limit(50)).all()
    return {
        'subscription':{
            'status':subscription.status if subscription else 'not_subscribed',
            'current_period_end':subscription.current_period_end if subscription else None,
            'cancel_at_period_end':subscription.cancel_at_period_end if subscription else False,
        },
        'invoices':[{
            'id':item.id,'amount_due':item.amount_due,'amount_paid':item.amount_paid,
            'currency':item.currency,'status':item.status,
            'hosted_invoice_url':item.hosted_invoice_url,'created_at':item.created_at,
        } for item in invoices]
    }

def _valid_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature:
        return False
    fields={}
    for part in signature.split(','):
        key,sep,value=part.partition('=')
        if sep:
            fields.setdefault(key,[]).append(value)
    try:
        timestamp=int(fields['t'][0])
    except (KeyError,ValueError,IndexError):
        return False
    if abs(time.time()-timestamp)>300:
        return False
    expected=hmac.new(secret.encode(),str(timestamp).encode()+b'.'+body,hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected,value) for value in fields.get('v1',[]))

@router.post('/webhook')
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None), db: Session = Depends(get_db)):
    settings=get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503,detail='Billing webhooks are not configured')
    body=await request.body()
    if len(body)>1024*1024 or not _valid_signature(body,stripe_signature,settings.stripe_webhook_secret):
        raise HTTPException(status_code=400,detail='Invalid Stripe webhook signature')
    try:
        event=json.loads(body)
        event_id=event['id']
        event_type=event['type']
        obj=event['data']['object']
    except (ValueError,KeyError,TypeError):
        raise HTTPException(status_code=400,detail='Malformed Stripe event')
    if db.scalar(select(ProcessedBillingWebhook.id).where(ProcessedBillingWebhook.stripe_event_id==event_id)):
        return {'received':True,'duplicate':True}
    user_id=None
    if event_type=='checkout.session.completed':
        raw_id=(obj.get('client_reference_id') or obj.get('metadata',{}).get('user_id'))
        try:
            user_id=int(raw_id)
        except (ValueError,TypeError):
            user_id=None
        if user_id and db.get(User,user_id):
            subscription=db.scalar(select(BillingSubscription).where(BillingSubscription.user_id==user_id))
            if subscription is None:
                subscription=BillingSubscription(user_id=user_id,stripe_price_id=settings.stripe_price_id or 'unknown')
                db.add(subscription)
            subscription.stripe_customer_id=obj.get('customer')
            subscription.stripe_subscription_id=obj.get('subscription')
            subscription.status='incomplete'
    elif event_type.startswith('customer.subscription.'):
        customer_id=obj.get('customer')
        stripe_sub_id=obj.get('id')
        raw_user_id=obj.get('metadata',{}).get('user_id')
        try:
            metadata_user_id=int(raw_user_id) if raw_user_id else None
        except (ValueError,TypeError):
            metadata_user_id=None
        subscription=db.scalar(select(BillingSubscription).where(
            (BillingSubscription.stripe_subscription_id==stripe_sub_id) |
            (BillingSubscription.stripe_customer_id==customer_id)))
        if subscription is None and metadata_user_id and db.get(User,metadata_user_id):
            subscription=BillingSubscription(user_id=metadata_user_id,stripe_price_id=settings.stripe_price_id or 'unknown')
            db.add(subscription)
        if subscription:
            user_id=subscription.user_id
            subscription.stripe_customer_id=customer_id
            subscription.stripe_subscription_id=stripe_sub_id
            subscription.status=obj.get('status','unknown')
            subscription.cancel_at_period_end=bool(obj.get('cancel_at_period_end',False))
            period_end=obj.get('current_period_end')
            subscription.current_period_end=datetime.fromtimestamp(period_end,timezone.utc) if period_end else None
            price_items=obj.get('items',{}).get('data',[])
            if price_items:
                subscription.stripe_price_id=price_items[0].get('price',{}).get('id',subscription.stripe_price_id)
    elif event_type in ('invoice.paid','invoice.payment_failed'):
        customer_id=obj.get('customer')
        subscription=db.scalar(select(BillingSubscription).where(BillingSubscription.stripe_customer_id==customer_id))
        if subscription:
            user_id=subscription.user_id
            invoice=db.scalar(select(BillingInvoice).where(BillingInvoice.stripe_invoice_id==obj.get('id')))
            if invoice is None:
                invoice=BillingInvoice(user_id=user_id,stripe_invoice_id=obj.get('id','unknown'))
                db.add(invoice)
            invoice.amount_due=int(obj.get('amount_due') or 0)
            invoice.amount_paid=int(obj.get('amount_paid') or 0)
            invoice.currency=(obj.get('currency') or 'usd')[:8]
            invoice.status='paid' if event_type=='invoice.paid' else 'payment_failed'
            invoice.hosted_invoice_url=obj.get('hosted_invoice_url')
    db.add(ProcessedBillingWebhook(stripe_event_id=event_id,event_type=event_type))
    if user_id:
        record_event(db,'billing.webhook.'+event_type,None,f'Processed Stripe event {event_id} for user {user_id}')
    db.commit()
    return {'received':True,'duplicate':False}
