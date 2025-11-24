import os
import json
import sys
import base64
# import sys
import logging
from urllib.parse import quote_plus, urlencode, quote, urlparse
from enum import Enum
from urllib.request import urlopen

from fastapi import FastAPI, Request, HTTPException, Depends, Path, Query
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pincrawl.database import Database, Watching, Product, Account, PLAN_WATCHING_LIMITS, Ad
from pincrawl.graph_utils import generate_price_graph
from pincrawl.i18n import I18n
from fastapi.exceptions import RequestValidationError
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
# from fastapi.middleware.trustedhost import TrustedHostMiddleware

from pincrawl.push_notification_service import PushNotificationService, NotSubscribedPushException

# Load environment variables
load_dotenv()

www_log_level = os.getenv("WWW_LOG_LEVEL", "info").upper()

logging.basicConfig(
    level=www_log_level,
    format='%(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logging.getLogger("pincrawl").setLevel(www_log_level)

# Setup logging
logger = logging.getLogger(__name__)

app = FastAPI(title="Pincrawl")

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
if not SESSION_SECRET_KEY:
    raise ValueError("SESSION_SECRET_KEY environment variable is required")

PINCRAWL_BASE_URL = os.getenv('PINCRAWL_BASE_URL')
if not PINCRAWL_BASE_URL:
    raise Exception("PINCRAWL_BASE_URL environment variable not set")
PINCRAWL_BASE_URL = PINCRAWL_BASE_URL.rstrip('/') # Remove trailing slash if it exists

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])
# app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "192-168-0-11.nip.io"])

# Mount static files
dist_dir = os.path.join(os.path.dirname(__file__), "dist")
app.mount("/dist", StaticFiles(directory=dist_dir), name="dist")

# Setup Jinja2 templates

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Add i18n context processor
def create_template_context(locale: str|None,  user: dict|None = None, account: Account|None = None, **kwargs):
    """Create template context with i18n support"""

    i18n_context = i18n.create_context(locale)
    context = {
        "locale": i18n_context.locale,
        "_": i18n_context._,  # Add simple _ function for Babel extraction
        "supported_locales": i18n.SUPPORTED_LOCALES,
        **kwargs
    }
    if account:
        context["account"] = account
    if user:
        context["user"] = user

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

# Create i18n instance
i18n = I18n(os.path.join(os.path.dirname(__file__), 'translations'))

@app.exception_handler(StarletteHTTPException)
async def auth_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle authentication exceptions by serving login page"""

    if exc.status_code in [401, 403]:
        # Extract locale from path or use default
        path_parts = request.url.path.strip('/').split('/')
        locale = path_parts[0] if path_parts and path_parts[0] else None

        return templates.TemplateResponse(
            request,
            "login.html",
            create_template_context(locale),
            status_code=exc.status_code
        )
    else:
        # For other HTTP exceptions, return default error page
        return templates.TemplateResponse(
            request,
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
                request,
                "error.html",
                {
                    "request": request,
                    "error_code": 404,
                    "error_message": "Not Found"
                }
            )

    # For other validation errors, return 400
    return templates.TemplateResponse(
        request,
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


def url_base64_to_bytes(base64_string):
    """Convert base64url string to bytes array for JavaScript"""
    if not base64_string:
        raise ValueError("Base64 string is empty or null")

    # Add padding if needed
    padding = '=' * ((4 - len(base64_string) % 4) % 4)
    base64_with_padding = base64_string + padding

    # Convert base64url to standard base64
    standard_base64 = base64_with_padding.replace('-', '+').replace('_', '/')

    try:
        # Decode to bytes
        raw_bytes = base64.b64decode(standard_base64)
        # Convert to list of integers for JSON serialization
        return list(raw_bytes)
    except Exception as e:
        raise ValueError(f"Failed to decode base64 string: {str(e)}")

# Public endpoint for graph generation
@app.get("/graphs/{product_opdb_id}.{format}")
async def get_graph(product_opdb_id: str, format: str):
    """Generate and serve price graph for a pinball machine.

    Generates the graph on-demand and caches it. If the cached graph is from
    a previous day, it will be regenerated.

    Args:
        product_opdb_id: The OPDB ID of the product
        format: The output format ('svg' or 'png')
    """
    # Validate format
    if format.lower() not in ['svg', 'png']:
        raise HTTPException(status_code=400, detail="Format must be 'svg' or 'png'")

    format = format.lower()

    # Define graph directory and paths
    graph_dir =  os.path.join(os.path.dirname(__file__), "var/graphs")
    os.makedirs(graph_dir, exist_ok=True)

    graph_path = os.path.join(graph_dir, f"{product_opdb_id}.{format}")
    nodata_graph_path = os.path.join(graph_dir, f"nodata.{format}")

    # Check if we need to regenerate the graph
    should_regenerate = True

    if os.path.exists(graph_path):
        # Check if the file was created today
        file_mtime = datetime.fromtimestamp(os.path.getmtime(graph_path))
        today = datetime.now().date()

        if file_mtime.date() == today:
            should_regenerate = False

    if should_regenerate:
        logger.info(f"Generating graph for product_opdb_id={product_opdb_id}")

        session = db.get_db()
        try:
            # Verify product exists
            product = session.query(Product).filter_by(opdb_id=product_opdb_id).first()
            if not product:
                # Product not found, return 404
                session.close()
                raise HTTPException(status_code=404, detail="Product not found")

            # Get date range for last year
            current_date = datetime.now()
            one_year_ago = current_date - timedelta(days=365)

            # Query ads for this product from the last year
            ads = session.query(Ad).filter(
                Ad.opdb_id == product.opdb_id,
                Ad.amount.isnot(None),
                Ad.currency == 'EUR',
                Ad.ignored == False,
                Ad.created_at >= one_year_ago
            ).order_by(Ad.created_at).all()

            if ads:
                # Prepare data for plotting
                # Build dots list: List[Tuple[datetime, price, id, next_id, is_end]]
                dots = [
                    (ad.created_at, ad.amount, ad.id, ad.next.id if ad.next else None, ad.next is None)
                    for ad in ads
                ]

                logger.info(f"Generated {len(dots)} data points for graph")

                # Generate the graph
                generate_price_graph(dots, graph_path, format=format)
                logger.info(f"✓ Generated graph for opdb_id={product_opdb_id} with {len(ads)} data points")
            else:
                # No data available, generate "no data" graph
                        # Check if nodata graph needs regeneration (once per day)
                should_regenerate_nodata = True

                if os.path.exists(nodata_graph_path):
                    nodata_mtime = datetime.fromtimestamp(os.path.getmtime(nodata_graph_path))
                    today = datetime.now().date()

                    if nodata_mtime.date() == today:
                        should_regenerate_nodata = False

                if should_regenerate_nodata:
                    generate_price_graph([],nodata_graph_path, format=format)
                    logger.info(f"✓ Generated/refreshed nodata graph ({format})")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error generating graph for opdb_id={product_opdb_id}: {str(e)}")
            session.close()
            raise HTTPException(status_code=500, detail="Failed to generate graph")
        finally:
            session.close()

    # Determine the media type based on format
    media_type = "image/svg+xml" if format == "svg" else "image/png"

    # Serve the graph file
    if os.path.exists(graph_path):
        return FileResponse(graph_path, media_type=media_type)
    else:
        return FileResponse(nodata_graph_path, media_type=media_type)

# Redirect root to default locale
@app.get("/")
async def root_redirect(
    request: Request,
):
    """Redirect root path to user's preferred locale based on browser language"""
    # Always use browser language for navigation
    locale = i18n.get_locale_from_accept_language(request.headers.get('accept-language', None))

    return RedirectResponse(url=f"/{locale}/")

@app.get("/{locale}/", response_class=HTMLResponse)
async def homepage(
    request: Request,
    locale: str = Path(..., pattern=i18n.get_supported_locales_pattern()),
):
    """Protected homepage - only for authenticated users"""

    user = get_user(request)
    account = None
    if user:
        account = Account.get_by_email(db.get_db(), user.get('email'))

    return templates.TemplateResponse(
        request,
        "home.html",
        create_template_context(locale, user=user, account=account)
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

            # Check if user account exists in database, create if not
            user_email = user_info.get('email')
            if user_email:
                session = db.get_db()
                try:
                    # Get or create account (automatically creates free plan if new)
                    account = Account.get_by_email(session, user_email)
                    if account is None:
                        # Detect browser language for new users (used for communication preferences)
                        browser_language = i18n.get_locale_from_accept_language(request.headers.get('accept-language', None))
                        account = Account.create_account(session, user_email, language=browser_language)
                        logger.info(f"✓ Created new account for user: {user_email} with communication language: {browser_language}")
                    else:
                        logger.info(f"✓ Found existing account for user: {user_email}")

                except Exception as e:
                    logger.error(f"❌ Error handling account for user {user_email}: {str(e)}")
                    session.close()
                    raise HTTPException(status_code=500, detail=f"Account creation failed: {str(e)}")
                finally:
                    session.close()

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
    locale: str = Path(..., pattern=i18n.get_supported_locales_pattern()),
    query: str = None,
    manufacturer: str = None,
    year_min: int = None,
    year_max: int = None,
    subscribed: bool = False,
    page: int = 1,
    user=Depends(get_authenticated_user)
):
    """Handle pinballs listing with pagination and search functionality"""

    logger.info(f"Products endpoint called with query='{query}', manufacturer='{manufacturer}', year_min={year_min}, year_max={year_max}, subscribed={subscribed}, page={page}")

    # Pagination settings
    offset = (page - 1) * PRODUCTS_PER_PAGE

    # Get user email and account
    user_email = user.get('email')
    account = None

    session = db.get_db()

    # Get account for subscription filtering
    account_id = None
    if user_email and subscribed:
        account = Account.get_by_email(session, user_email)
        if account:
            account_id = account.id

    # get products
    products, total = Product.fetch(
        session,
        query=query,
        manufacturer=manufacturer,
        year_min=year_min,
        year_max=year_max,
        subscribed_only_account_id=account_id,
        offset=offset,
        limit=PRODUCTS_PER_PAGE
    )

    # Enrich products with subscription status
    # Also get manufacturers and year range using the same database session
    try:
        user_watching = set()
        if user_email:
            account = Account.get_by_email(session, user_email)
            if account:
                user_watching = Watching.get_user_watching(session, account.id)

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
        request,
        "pinballs.html",
        create_template_context(
            locale,
            user=user,
            account=account,
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
            next_page=page + 1 if page < total_pages else None,
            user_watching=user_watching
        )
    )


@app.get("/{locale}/plans")
async def plans(
    request: Request,
    locale: str = Path(..., pattern=i18n.get_supported_locales_pattern()),
    user=Depends(get_authenticated_user)
):
    """Handle plans page"""

    # Get user's current plan to show appropriate buttons
    user_email = user.get('email')
    current_plan = None
    account = None

    if user_email:
        session = db.get_db()
        try:
            # Get account information and current plan
            account = Account.get_by_email(session, user_email)
            if account:
                current_plan = account.get_current_plan(session)
        except Exception as e:
            logger.error(f"❌ Error fetching plan information for user {user_email}: {str(e)}")
            # Continue without plan info rather than failing
        finally:
            session.close()

    return templates.TemplateResponse(
        request,
        "plans.html",
        create_template_context(
            locale,
            user=user,
            account=account,
            current_plan=current_plan
        )
    )


@app.get("/{locale}/legal-notice")
async def legal_notice(
    request: Request,
    locale: str = Path(..., pattern=i18n.get_supported_locales_pattern())
):
    """Handle legal notice page"""

    # Select template based on locale
    template_name = f"legal-notice.{locale}.html"

    user = get_user(request)
    account = None
    if user:
        account = Account.get_by_email(db.get_db(), user.get('email'))

    return templates.TemplateResponse(
        request,
        template_name,
        create_template_context(
            locale,
            user=user,
            account=account
        )
    )


@app.get("/{locale}/terms-of-use")
async def terms_of_service(
    request: Request,
    locale: str = Path(..., pattern=i18n.get_supported_locales_pattern())
):
    """Handle terms of use page (CGU)"""

    # Select template based on locale
    template_name = f"terms-of-use.{locale}.html"

    user = get_user(request)
    account = None
    if user:
        account = Account.get_by_email(db.get_db(), user.get('email'))

    return templates.TemplateResponse(
        request,
        template_name,
        create_template_context(
            locale,
            user=user,
            account=account
        )
    )


@app.get("/{locale}/my-account")
async def my_account(
    request: Request,
    locale: str = Path(..., pattern=i18n.get_supported_locales_pattern()),
    user=Depends(get_authenticated_user)
):
    """Handle my account page"""

    # Get user email and account information
    user_email = user.get('email')
    account = None
    current_plan = None

    if user_email:
        session = db.get_db()
        try:
            # Get account information
            account = Account.get_by_email(session, user_email)
            if account:
                current_plan = account.get_current_plan(session)
        except Exception as e:
            logger.error(f"❌ Error fetching account information for user {user_email}: {str(e)}")
            # Continue without account info rather than failing
        finally:
            session.close()

    return templates.TemplateResponse(
        request,
        "my-account.html",
        create_template_context(
            locale,
            user=user,
            account=account,
            current_plan=current_plan
        )
    )


@app.put("/api/my-account")
async def update_my_account(
    request: Request,
    user=Depends(get_authenticated_user)
):
    """Update account preferences, push subscriptions, and email preferences"""
    user_email = user.get('email')

    data = await request.json()

    session = db.get_db()

    try:
        account = Account.get_by_email(session, user_email)
        if not account:
            raise HTTPException(status_code=400, detail="User account not found")

        # Update language preference if provided
        if 'language' in data:
            language = data.get('language')
            if language not in i18n.SUPPORTED_LOCALES:
                raise HTTPException(status_code=400, detail="Invalid language")
            account.language = language
            logger.info(f"✓ Updated language for user {user_email} to {language}")

        # Update email preference if provided
        if 'email_notifications' in data:
            email_notifications = data.get('email_notifications')
            if not isinstance(email_notifications, bool):
                raise HTTPException(status_code=400, detail="Invalid email_notifications value")
            account.email_notifications = email_notifications
            logger.info(f"✓ Updated email_notifications for user {user_email} to {email_notifications}")

        session.commit()

        return JSONResponse(content={'success': True})

    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Error updating account for user {user_email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()

@app.post("/api/test-push-notification")
async def test_push_notification(
    request: Request,
    user=Depends(get_authenticated_user)
):
    """Send a test push notification to the authenticated user"""

    user_email = user.get('email')

    session = db.get_db()

    try:
        # Find account by email
        account = Account.get_by_email(session, user_email)
        if not account:
            raise HTTPException(status_code=400, detail="Account not found")

        current_plan = account.get_current_plan(session)
        if not current_plan or not current_plan.is_granted_for_push():
            raise HTTPException(status_code=402, detail="Push notifications not allowed for this account due to plan restrictions")

        push_notification_service = PushNotificationService(i18n)

        i18n_context = i18n.create_context(account.language)

        try:
            push_notification_service.send_notification(
                remote_ids=[str(account.remote_id)],
                title=i18n_context._("Test notification from PINCRAWL"),
                body=i18n_context._("This is a test push notification to verify it is working correctly."),
                url=PINCRAWL_BASE_URL
            )
        except NotSubscribedPushException as e:
            logger.info(f"Account {user_email} is not subscribed for push notifications: {e}")
            raise HTTPException(status_code=400, detail="Push notification test failed: User not subscribed")

        logger.info(f"✓ Test push notification sent successfully to {user_email}")

        return JSONResponse(content={'success': True})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error sending test push notification to {user_email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send test notification")
    finally:
        session.close()

@app.post("/api/watch")
async def watch(
    request: Request,
    user=Depends(get_authenticated_user)
):

    # Get user email
    user_email = user.get('email')
    session = db.get_db()

    account = Account.get_by_email(session, user_email)
    if not account:
        raise HTTPException(status_code=400, detail="User account not found")

    data = await request.json()
    id = data.get("id")
    if not id:
        raise HTTPException(status_code=400, detail="Missing 'id' in request body")

    product = session.query(Product).filter_by(id=id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Pinball not found")

    # Check if subscription already exists
    existing = session.query(Watching).filter_by(
        account_id=account.id,
        opdb_id=product.opdb_id
    ).first()

    if existing:
        session.delete(existing)
        logger.info(f"✗ Removed subscription: {user_email} -> {product.opdb_id}")
        status = 202  # Accepted (deleted)
    else:
        # Check plan limits before adding new subscription
        try:
            current_plan = account.get_current_plan(session)
            if not current_plan:
                raise HTTPException(status_code=500, detail="No active plan found")

            # Get current number of watching subscriptions
            current_watching_count = session.query(Watching).filter_by(account_id=account.id).count()

            # Check plan limit
            plan_limit = PLAN_WATCHING_LIMITS.get(current_plan.plan, 0)

            if current_watching_count >= plan_limit:
                session.close()
                raise HTTPException(
                    status_code=402,  # Payment Required
                    detail=f"Watching limit reached for {current_plan.plan.value} plan ({plan_limit} pinballs max)"
                )

            # Create new subscription
            subscription = Watching(account_id=account.id, opdb_id=product.opdb_id)
            session.add(subscription)
            logger.info(f"✓ Added subscription: {user_email} -> {product.opdb_id}")
            status = 201  # Created

        except HTTPException:
            session.close()
            raise
        except Exception as e:
            session.close()
            logger.error(f"❌ Error checking plan limits for user {user_email}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    session.commit()
    session.close()

    return JSONResponse(status_code=status, content={'success': True})