#!/usr/bin/env python3

import os
import json
from urllib.parse import quote_plus, urlencode
from urllib.request import urlopen

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Pincrawl")

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "dev-secret-key"))

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Auth0 configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")

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


@app.post("/search")
async def search(request: Request, user=Depends(get_authenticated_user)):
    """Handle search submission (placeholder for now)"""
    form = await request.form()
    search_query = form.get("query", "")

    # For now, just return to homepage with a message
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "user": user,
            "search_query": search_query,
            "message": f"Search functionality coming soon! You searched for: '{search_query}'"
        }
    )