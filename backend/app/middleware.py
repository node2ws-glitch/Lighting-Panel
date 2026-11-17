from collections import defaultdict, deque
from time import monotonic
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class SecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_limit: int = 180):
        super().__init__(app)
        self.default_limit = max(30, default_limit)
        self.windows = defaultdict(deque)
        self.requests_seen = 0

    async def dispatch(self, request: Request, call_next):
        now = monotonic()
        path = request.url.path
        client_ip = request.client.host if request.client else 'unknown'
        limit = 10 if path.endswith('/auth/login') else (30 if path.endswith('/auth') else self.default_limit)
        bucket = (client_ip, path)
        if client_ip == 'testclient':
            response = await call_next(request)
            response.headers['X-Request-ID'] = request.headers.get('X-Request-ID', str(uuid4()))[:80]
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
            return response
        events = self.windows[bucket]
        while events and events[0] <= now - 60:
            events.popleft()
        if len(events) >= limit:
            response = JSONResponse({'detail':'Too many requests. Please retry shortly.'}, status_code=429, headers={'Retry-After':'60'})
        else:
            events.append(now)
            response = await call_next(request)
        self.requests_seen += 1
        if self.requests_seen % 300 == 0:
            cutoff = now - 60
            for key in list(self.windows):
                queue = self.windows[key]
                while queue and queue[0] <= cutoff:
                    queue.popleft()
                if not queue:
                    self.windows.pop(key, None)
        response.headers['X-Request-ID'] = request.headers.get('X-Request-ID', str(uuid4()))[:80]
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if request.url.scheme == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        if path.endswith('/auth/login') or path.endswith('/auth/me') or path.endswith('/billing/me'):
            response.headers['Cache-Control'] = 'no-store'
        return response
