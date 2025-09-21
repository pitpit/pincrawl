#!/usr/bin/env python3

import os
import json
import sys
# import sys
import logging
from urllib.parse import quote_plus, urlencode
from urllib.request import urlopen

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from pincrawl.product_matcher import ProductMatcher
from pincrawl.database import Database, Sub, Product

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
db.init_db()

@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    """Handle authentication exceptions by serving login page"""
    if exc.status_code in [401, 403]:
        return templates.TemplateResponse(
            "login.html",
            {"request": request},
            status_code=exc.status_code
        )
    raise exc


def get_user(request: Request):
    """Get the current user from session, return None if not authenticated"""
    return request.session.get("user")


def get_authenticated_user(request: Request):
    """Get the current user from session, redirect to login if not authenticated"""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request, user=Depends(get_authenticated_user)):
    """Protected homepage - only for authenticated users"""
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "user": user}
    )

@app.get("/login")
async def login(request: Request):
    """Initiate Auth0 login"""
    redirect_uri = request.url_for('callback')
    return await oauth.auth0.authorize_redirect(request, redirect_uri)


@app.get("/callback")
async def callback(request: Request):
    """Handle Auth0 callback"""
    try:
        token = await oauth.auth0.authorize_access_token(request)
        user_info = token.get('userinfo')

        if user_info:
            request.session['user'] = dict(user_info)

        return RedirectResponse(url="/")
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
            "returnTo": request.url_for('homepage'),
            "client_id": AUTH0_CLIENT_ID
        }, quote_via=quote_plus)
    )

    return RedirectResponse(url=auth0_logout_url)


@app.get("/pinballs")
async def products(request: Request, query: str = None, manufacturer: str = None, year_min: int = None, year_max: int = None, subscribed: bool = False, page: int = 1, user=Depends(get_authenticated_user)):
    """Handle pinballs listing with pagination and search functionality"""

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
        "products.html",
        {
            "request": request,
            "user": user,
            "products": products,
            "manufacturers": manufacturers,
            "query": query,
            "selected_manufacturer": manufacturer,
            "year_min": year_min,
            "year_max": year_max,
            "subscribed": subscribed,
            "min_year": year_range['min_year'],
            "max_year": year_range['max_year'],
            "current_page": page,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_page": page - 1 if page > 1 else None,
            "next_page": page + 1 if page < total_pages else None
        }
    )


@app.post("/subs")
async def products(request: Request, user=Depends(get_authenticated_user)):

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
