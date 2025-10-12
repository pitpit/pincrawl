#!/usr/bin/env python3

import os
import json
import sys
# import sys
import logging
from urllib.parse import quote_plus, urlencode, quote, urlparse
from enum import Enum
from urllib.request import urlopen

from fastapi import FastAPI, Request, HTTPException, Depends, Path, Query
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from pincrawl.product_matcher import ProductMatcher
from pincrawl.database import Database, Sub, Product
from i18n import get_locale_from_request, validate_locale, I18nContext, SUPPORTED_LOCALES, DEFAULT_LOCALE
from fastapi.exceptions import RequestValidationError

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Setup logging
logger = logging.getLogger(__name__)
# logging.getLogger("pincrawl").setLevel(logging.DEBUG)

app = FastAPI(title="Pincrawl")

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
if not SESSION_SECRET_KEY:
    raise ValueError("SESSION_SECRET_KEY environment variable is required")

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Add i18n context processor
def create_template_context(request: Request, locale: str, **kwargs):
    """Create template context with i18n support"""
    context = {
        "request": request,
        "locale": locale,
        "i18n": I18nContext(locale),
        "supported_locales": SUPPORTED_LOCALES,
        **kwargs
    }
    return context

# Auth0 configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")

PRODUCTS_PER_PAGE = os.getenv("PRODUCTS_PER_PAGE", 20)

# Validate Auth0 configuration
if not AUTH0_DOMAIN:
    raise ValueError("AUTH0_DOMAIN environment variable is required")
if not AUTH0_CLIENT_ID:
    raise ValueError("AUTH0_CLIENT_ID environment variable is required")
if not AUTH0_CLIENT_SECRET:
    raise ValueError("AUTH0_CLIENT_SECRET environment variable is required")

oauth = OAuth()
oauth.register(
    "auth0",
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{AUTH0_DOMAIN}/.well-known/openid-configuration'
)

db = Database()

@app.exception_handler(StarletteHTTPException)
async def auth_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle authentication exceptions by serving login page"""

    if exc.status_code in [401, 403]:
        # Extract locale from path or use default
        path_parts = request.url.path.strip('/').split('/')
        locale = path_parts[0] if path_parts and path_parts[0] in SUPPORTED_LOCALES else DEFAULT_LOCALE

        return templates.TemplateResponse(
            "login.html",
            create_template_context(request, locale),
            status_code=exc.status_code
        )
    else:
        # For other HTTP exceptions, return default error page
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": exc.status_code,
                "error_message": exc.detail
            },
            status_code=exc.status_code
        )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors, particularly for unsupported locales"""

    # Check if this is a locale validation error
    for error in exc.errors():
        if (error.get("loc") and
            len(error["loc"]) >= 2 and
            error["loc"][0] == "path" and
            error["loc"][1] == "locale" and
            error.get("type") == "string_pattern_mismatch"):

            # This is an unsupported locale, return 404
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error_code": 404,
                    "error_message": "Not Found"
                }
            )

    # For other validation errors, return 400
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error_code": 400,
            "error_message": "Invalid request"
        },
        status_code=400
    )

def get_user(request: Request):
    """Get the current user from session, return None if not authenticated"""
    return request.session.get("user")


def get_authenticated_user(request: Request):
    """Get the current user from session, redirect to login if not authenticated"""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# Redirect root to default locale
@app.get("/")
async def root_redirect(request: Request):
    """Redirect root path to user's preferred locale based on browser language"""
    # Get browser's preferred language from Accept-Language header
    accept_language = request.headers.get('accept-language', '')
    locale = DEFAULT_LOCALE

    if accept_language:
        # Parse Accept-Language header (format: "en-US,en;q=0.9,fr;q=0.8")
        try:
            # Split by comma and get the first preference
            languages = accept_language.split(',')
            for lang in languages:
                # Remove quality factor (;q=0.9) if present
                lang_code = lang.split(';')[0].strip().lower()

                # Extract just the language part (before any country code)
                primary_lang = lang_code.split('-')[0]

                # Check if this language is supported
                if primary_lang in SUPPORTED_LOCALES:
                    locale = primary_lang
                    break
        except:
            # If parsing fails, use default
            locale = DEFAULT_LOCALE

    return RedirectResponse(url=f"/{locale}/")

class LocaleName(str, Enum):
    fr = "fr"
    en = "en"


@app.get("/{locale}/", response_class=HTMLResponse)
async def homepage(
    request: Request,
    locale: str = Path(..., pattern=f"^({'|'.join(SUPPORTED_LOCALES)})$"),
    user=Depends(get_authenticated_user)
):
    """Protected homepage - only for authenticated users"""
    locale = validate_locale(locale)
    return templates.TemplateResponse(
        "home.html",
        create_template_context(request, locale, user=user)
    )

@app.get("/login")
async def login(
    request: Request
):
    """Initiate Auth0 login"""

    # Get the current page URL as the redirect target
    # Use the referer header to determine where user came from
    redirect_after_login = request.url_for('root_redirect')  # Default fallback

    referer = request.headers.get('referer', '')
    if referer:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            # Use the path from referer if it's from same domain
            if parsed.path and parsed.path != '/login':
                redirect_after_login = parsed.path
                # Include query parameters if they exist
                if parsed.query:
                    redirect_after_login += f"?{parsed.query}"
        except:
            # If parsing fails, use default
            pass

    redirect_uri = str(request.url_for('callback')) + f"?redirect_after_login={quote(redirect_after_login)}"
    return await oauth.auth0.authorize_redirect(request, redirect_uri)


@app.get("/callback")
async def callback(
    request: Request,
    redirect_after_login: str = Query(None)
):
    """Handle Auth0 callback"""
    try:
        token = await oauth.auth0.authorize_access_token(request)
        user_info = token.get('userinfo')

        if user_info:
            request.session['user'] = dict(user_info)

        # Validate and sanitize redirect_after_login for security
        redirect_target = request.url_for('root_redirect')  # Default fallback

        if redirect_after_login:

            try:
                parsed = urlparse(redirect_after_login)
                # Only allow relative URLs (no scheme, no netloc)
                if not parsed.scheme and not parsed.netloc and parsed.path:
                    # Ensure path starts with / and is valid
                    if parsed.path.startswith('/') and len(parsed.path) > 1:
                        redirect_target = redirect_after_login
            except:
                # If parsing fails, use default
                pass

        return RedirectResponse(url=redirect_target)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@app.get("/logout")
async def logout(request: Request):
    """Logout and clear session"""
    request.session.clear()

    # Redirect to Auth0 logout
    auth0_logout_url = (
        f"https://{AUTH0_DOMAIN}/v2/logout?"
        + urlencode({
            "returnTo": request.url_for('root_redirect'),
            "client_id": AUTH0_CLIENT_ID
        }, quote_via=quote_plus)
    )

    return RedirectResponse(url=auth0_logout_url)


@app.get("/{locale}/pinballs")
async def pinballs(
    request: Request,
    locale: str = Path(..., pattern=f"^({'|'.join(SUPPORTED_LOCALES)})$"),
    query: str = None,
    manufacturer: str = None,
    year_min: int = None,
    year_max: int = None,
    subscribed: bool = False,
    page: int = 1,
    user=Depends(get_authenticated_user)
):
    """Handle pinballs listing with pagination and search functionality"""
    locale = validate_locale(locale)

    logger.info(f"Products endpoint called with query='{query}', manufacturer='{manufacturer}', year_min={year_min}, year_max={year_max}, subscribed={subscribed}, page={page}")

    # Pagination settings
    offset = (page - 1) * PRODUCTS_PER_PAGE

    # Get user email for subscription filtering
    user_email = user.get('email')

    session = db.get_db()

    # Initialize ProductMatcher and get products
    products, total = Product.fetch(
        session,
        query=query,
        manufacturer=manufacturer,
        year_min=year_min,
        year_max=year_max,
        subscribed_only_user_email=user_email if subscribed else None,
        offset=offset,
        limit=PRODUCTS_PER_PAGE
    )

    # Enrich products with subscription status
    # Also get manufacturers and year range using the same database session
    try:
        if user_email:
            user_subscriptions = Sub.get_user_subscriptions(session, user_email)
            for product in products:
                product.is_subscribed = product.opdb_id in user_subscriptions
        else:
            # Mark all as not subscribed if no user email
            for product in products:
                product.is_subscribed = False

        # Get list of all manufacturers for dropdown
        manufacturers = Product.get_manufacturers(session)

        # Get year range for slider
        year_range = Product.get_year_range(session)

    finally:
        session.close()
        db.close_db()

    # Calculate pagination
    total_pages = total // PRODUCTS_PER_PAGE
    total_pages = 1 if total_pages == 0 else total_pages

    return templates.TemplateResponse(
        "pinballs.html",
        create_template_context(
            request,
            locale,
            user=user,
            products=products,
            manufacturers=manufacturers,
            query=query,
            selected_manufacturer=manufacturer,
            year_min=year_min,
            year_max=year_max,
            subscribed=subscribed,
            min_year=year_range['min_year'],
            max_year=year_range['max_year'],
            current_page=page,
            total_pages=total_pages,
            has_prev=page > 1,
            has_next=page < total_pages,
            prev_page=page - 1 if page > 1 else None,
            next_page=page + 1 if page < total_pages else None
        )
    )


@app.post("/subs")
async def subs(
    request: Request,
    user=Depends(get_authenticated_user)
):

    # Get user email for subscription filtering
    user_email = user.get('email')
    session = db.get_db()

    data = await request.json()
    id = data.get("id")
    if not id:
        raise HTTPException(status_code=400, detail="Missing 'id' in request body")

    product = session.query(Product).filter_by(id=id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Pinball not found")

    # Check if subscription already exists
    existing = session.query(Sub).filter_by(
        email=user_email,
        opdb_id=product.opdb_id
    ).first()

    if existing:
        session.delete(existing)
        logger.info(f"✗ Removed subscription: {user_email} -> {product.opdb_id}")
        status = 202  # Accepted (deleted)
    else:
        # Create new subscription
        subscription = Sub(email=user_email, opdb_id=product.opdb_id)
        session.add(subscription)
        logger.info(f"✓ Added subscription: {user_email} -> {product.opdb_id}")
        status = 201  # Created

    session.commit()
    session.close()

    return HTMLResponse(status_code=status, content="")
