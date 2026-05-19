from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from loguru import logger
from app.database.db import init_db

limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>WebAnalyzer v3 API Docs</title>

  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />

  <style>
    body {
      margin: 0;
      padding: 0;
      background: #0b1020;
    }

    #swagger-ui {
      min-height: 100vh;
    }

    .fallback {
      display: none;
      padding: 24px;
      color: #e5e7eb;
      font-family: Arial, sans-serif;
      line-height: 1.6;
    }

    .fallback a {
      color: #4fffb0;
    }
  </style>
</head>

<body>
  <div id="swagger-ui"></div>

  <div class="fallback" id="fallback">
    <h1>WebAnalyzer v3 API</h1>
    <p>Swagger UI не завантажився. Можливо, CDN тимчасово недоступний.</p>
    <p>
      OpenAPI JSON:
      <a href="{{ spec_url }}">{{ spec_url }}</a>
    </p>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>

  <script>
    window.onload = function() {
      if (typeof SwaggerUIBundle === 'undefined') {
        document.getElementById('fallback').style.display = 'block';
        return;
      }

      SwaggerUIBundle({
        url: "{{ spec_url }}",
        dom_id: "#swagger-ui",
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout",
        deepLinking: true,
        tryItOutEnabled: true
      });
    };
  </script>
</body>
</html>"""

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "WebAnalyzer v3 API",
        "version": "3.0.0",
        "description": (
            "API for WebAnalyzer v3: authentication, AI analysis, history, "
            "exports, sharing, tags, collections, statistics and health checks."
        ),
    },
    "tags": [
        {"name": "Auth", "description": "User registration, login and JWT cookies"},
        {"name": "Profile", "description": "User profile, API keys and theme"},
        {"name": "Analysis", "description": "AI web analysis pipeline"},
        {"name": "History", "description": "Saved analysis results"},
        {"name": "Export", "description": "JSON, Markdown and PDF export"},
        {"name": "Share", "description": "Public share links"},
        {"name": "Tags", "description": "Tags for history items"},
        {"name": "Collections", "description": "Collections of saved analyses"},
        {"name": "Compare", "description": "Compare 2-3 saved analyses"},
        {"name": "Stats", "description": "User statistics"},
        {"name": "System", "description": "Health and service status"},
    ],
    "components": {
        "securitySchemes": {
            "cookieAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": "access_token",
                "description": "JWT access token stored in httpOnly cookie",
            }
        },
        "schemas": {
            "Error": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "example": "Помилка"}
                },
            },
            "User": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "email": {"type": "string", "example": "user@example.com"},
                    "theme": {"type": "string", "example": "dark"},
                },
            },
            "AnalysisRequest": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "example": "Квантові комп'ютери",
                    },
                    "depth": {
                        "type": "string",
                        "enum": ["fast", "standard", "deep"],
                        "example": "standard",
                    },
                    "lang": {
                        "type": "string",
                        "enum": ["auto", "ru", "uk", "en"],
                        "example": "auto",
                    },
                },
            },
            "Sentiment": {
                "type": "object",
                "properties": {
                    "overall": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral", "mixed"],
                    },
                    "positive": {"type": "number", "example": 0.7},
                    "negative": {"type": "number", "example": 0.1},
                    "neutral": {"type": "number", "example": 0.2},
                    "explanation": {"type": "string"},
                },
            },
            "Source": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "domain": {"type": "string"},
                },
            },
            "AnalysisResult": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 10},
                    "query": {"type": "string"},
                    "summary": {"type": "string"},
                    "sentiment": {"$ref": "#/components/schemas/Sentiment"},
                    "overall": {"type": "string"},
                    "key_facts": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "sources": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Source"},
                    },
                    "sources_cnt": {"type": "integer"},
                    "depth": {"type": "string"},
                    "lang": {"type": "string"},
                    "created_at": {"type": "string"},
                },
            },
            "Tag": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "color": {"type": "string", "example": "#4fffb0"},
                },
            },
            "Collection": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "count": {"type": "integer"},
                },
            },
        },
    },
    "paths": {
        "/api/v1/auth/register": {
            "post": {
                "tags": ["Auth"],
                "summary": "Register a new user",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "password"],
                                "properties": {
                                    "email": {
                                        "type": "string",
                                        "example": "user@example.com",
                                    },
                                    "password": {
                                        "type": "string",
                                        "example": "password123",
                                    },
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "201": {"description": "User created"},
                    "400": {
                        "description": "Invalid input",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"}
                            }
                        },
                    },
                    "409": {"description": "Email already registered"},
                },
            }
        },
        "/api/v1/auth/login": {
            "post": {
                "tags": ["Auth"],
                "summary": "Login and set httpOnly JWT cookies",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "password"],
                                "properties": {
                                    "email": {
                                        "type": "string",
                                        "example": "user@example.com",
                                    },
                                    "password": {
                                        "type": "string",
                                        "example": "password123",
                                    },
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {"description": "Logged in"},
                    "401": {"description": "Invalid credentials"},
                },
            }
        },
        "/api/v1/auth/refresh": {
            "post": {
                "tags": ["Auth"],
                "summary": "Refresh access token using refresh cookie",
                "responses": {
                    "200": {"description": "Token refreshed"},
                    "401": {"description": "Refresh token missing or invalid"},
                },
            }
        },
        "/api/v1/auth/logout": {
            "post": {
                "tags": ["Auth"],
                "summary": "Logout and clear auth cookies",
                "responses": {"200": {"description": "Logged out"}},
            }
        },
        "/api/v1/auth/me": {
            "get": {
                "tags": ["Auth"],
                "summary": "Get current authenticated user",
                "security": [{"cookieAuth": []}],
                "responses": {
                    "200": {
                        "description": "Current user",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        },
                    },
                    "401": {"description": "Unauthorized"},
                },
            }
        },
        "/api/v1/profile/keys": {
            "get": {
                "tags": ["Profile"],
                "summary": "List saved API key providers",
                "security": [{"cookieAuth": []}],
                "responses": {"200": {"description": "API keys list"}},
            },
            "post": {
                "tags": ["Profile"],
                "summary": "Save encrypted AI provider API key",
                "security": [{"cookieAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["provider", "key"],
                                "properties": {
                                    "provider": {
                                        "type": "string",
                                        "enum": ["gemini", "groq", "ollama"],
                                    },
                                    "key": {"type": "string"},
                                    "model": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {"description": "Key saved"},
                    "400": {"description": "Invalid provider or empty key"},
                    "401": {"description": "Unauthorized"},
                },
            },
        },
        "/api/v1/profile/keys/{provider}": {
            "delete": {
                "tags": ["Profile"],
                "summary": "Delete API key by provider",
                "security": [{"cookieAuth": []}],
                "parameters": [
                    {
                        "name": "provider",
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": ["gemini", "groq", "ollama"],
                        },
                    }
                ],
                "responses": {"200": {"description": "Deleted"}},
            }
        },
        "/api/v1/profile/theme": {
            "post": {
                "tags": ["Profile"],
                "summary": "Save user theme",
                "security": [{"cookieAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "theme": {
                                        "type": "string",
                                        "example": "cyberpunk",
                                    }
                                },
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Theme saved"}},
            }
        },
        "/api/v1/analyze": {
            "post": {
                "tags": ["Analysis"],
                "summary": "Start AI analysis task",
                "security": [{"cookieAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/AnalysisRequest"
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Task queued or sync result returned",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "oneOf": [
                                        {
                                            "type": "object",
                                            "properties": {
                                                "task_id": {"type": "string"},
                                                "status": {
                                                    "type": "string",
                                                    "example": "queued",
                                                },
                                            },
                                        },
                                        {
                                            "$ref": "#/components/schemas/AnalysisResult"
                                        },
                                    ]
                                }
                            }
                        },
                    },
                    "400": {"description": "Bad request"},
                    "401": {"description": "Unauthorized"},
                    "429": {"description": "Rate limit exceeded"},
                },
            }
        },
        "/api/v1/task/{task_id}": {
            "get": {
                "tags": ["Analysis"],
                "summary": "Get Celery task status",
                "parameters": [
                    {
                        "name": "task_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"description": "Task status"}},
            }
        },
        "/api/v1/stream/{task_id}": {
            "get": {
                "tags": ["Analysis"],
                "summary": "Stream task progress using Server-Sent Events",
                "parameters": [
                    {
                        "name": "task_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "SSE progress stream",
                        "content": {
                            "text/event-stream": {
                                "schema": {"type": "string"}
                            }
                        },
                    }
                },
            }
        },
        "/api/v1/history": {
            "get": {
                "tags": ["History"],
                "summary": "List current user's analysis history",
                "security": [{"cookieAuth": []}],
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 20},
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "schema": {"type": "integer", "default": 0},
                    },
                    {
                        "name": "tag_id",
                        "in": "query",
                        "schema": {"type": "integer"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "History list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/components/schemas/AnalysisResult"
                                    },
                                }
                            }
                        },
                    },
                    "401": {"description": "Unauthorized"},
                },
            }
        },
        "/api/v1/history/{search_id}": {
            "get": {
                "tags": ["History"],
                "summary": "Get one saved analysis",
                "security": [{"cookieAuth": []}],
                "parameters": [
                    {
                        "name": "search_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Analysis result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/AnalysisResult"
                                }
                            }
                        },
                    },
                    "404": {"description": "Not found"},
                },
            },
            "delete": {
                "tags": ["History"],
                "summary": "Delete one saved analysis",
                "security": [{"cookieAuth": []}],
                "parameters": [
                    {
                        "name": "search_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {"200": {"description": "Deleted"}},
            },
        },
        "/api/v1/history/{search_id}/export/{fmt}": {
            "get": {
                "tags": ["Export"],
                "summary": "Export saved analysis as JSON, Markdown or PDF",
                "security": [{"cookieAuth": []}],
                "parameters": [
                    {
                        "name": "search_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                    {
                        "name": "fmt",
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": ["json", "markdown", "pdf"],
                        },
                    },
                ],
                "responses": {
                    "200": {"description": "Exported file"},
                    "400": {"description": "Unknown format"},
                    "404": {"description": "Not found"},
                },
            }
        },
        "/api/v1/history/{search_id}/share": {
            "post": {
                "tags": ["Share"],
                "summary": "Create public share link for 7 days",
                "security": [{"cookieAuth": []}],
                "parameters": [
                    {
                        "name": "search_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {"200": {"description": "Share link created"}},
            }
        },
        "/api/v1/share/{token}": {
            "get": {
                "tags": ["Share"],
                "summary": "Open public shared analysis",
                "parameters": [
                    {
                        "name": "token",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Shared analysis",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/AnalysisResult"
                                }
                            }
                        },
                    },
                    "404": {"description": "Invalid or expired link"},
                },
            }
        },
        "/api/v1/tags": {
            "get": {
                "tags": ["Tags"],
                "summary": "List user tags",
                "security": [{"cookieAuth": []}],
                "responses": {"200": {"description": "Tags list"}},
            },
            "post": {
                "tags": ["Tags"],
                "summary": "Create tag",
                "security": [{"cookieAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string", "example": "AI"},
                                    "color": {
                                        "type": "string",
                                        "example": "#4fffb0",
                                    },
                                },
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Tag created"}},
            },
        },
        "/api/v1/tags/{tag_id}": {
            "delete": {
                "tags": ["Tags"],
                "summary": "Delete tag",
                "security": [{"cookieAuth": []}],
                "parameters": [
                    {
                        "name": "tag_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {"200": {"description": "Deleted"}},
            }
        },
        "/api/v1/history/{search_id}/tags/{tag_id}": {
            "post": {
                "tags": ["Tags"],
                "summary": "Attach tag to analysis",
                "security": [{"cookieAuth": []}],
                "parameters": [
                    {
                        "name": "search_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                    {
                        "name": "tag_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                ],
                "responses": {"200": {"description": "Tag attached"}},
            },
            "delete": {
                "tags": ["Tags"],
                "summary": "Remove tag from analysis",
                "security": [{"cookieAuth": []}],
                "parameters": [
                    {
                        "name": "search_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                    {
                        "name": "tag_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                ],
                "responses": {"200": {"description": "Tag removed"}},
            },
        },
        "/api/v1/collections": {
            "get": {
                "tags": ["Collections"],
                "summary": "List collections",
                "security": [{"cookieAuth": []}],
                "responses": {"200": {"description": "Collections list"}},
            },
            "post": {
                "tags": ["Collections"],
                "summary": "Create collection",
                "security": [{"cookieAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Collection created"}},
            },
        },
        "/api/v1/collections/{col_id}/add/{search_id}": {
            "post": {
                "tags": ["Collections"],
                "summary": "Add analysis to collection",
                "security": [{"cookieAuth": []}],
                "parameters": [
                    {
                        "name": "col_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                    {
                        "name": "search_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                ],
                "responses": {"200": {"description": "Added"}},
            }
        },
        "/api/v1/compare": {
            "post": {
                "tags": ["Compare"],
                "summary": "Compare 2-3 saved analyses",
                "security": [{"cookieAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["ids"],
                                "properties": {
                                    "ids": {
                                        "type": "array",
                                        "minItems": 2,
                                        "maxItems": 3,
                                        "items": {"type": "integer"},
                                        "example": [1, 2],
                                    }
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {"description": "Comparison result"},
                    "400": {"description": "Invalid ids"},
                    "404": {"description": "One or more analyses not found"},
                },
            }
        },
        "/api/v1/stats": {
            "get": {
                "tags": ["Stats"],
                "summary": "Get current user's statistics",
                "security": [{"cookieAuth": []}],
                "responses": {"200": {"description": "Statistics"}},
            }
        },
        "/api/v1/health": {
            "get": {
                "tags": ["System"],
                "summary": "Health check for DB, Redis and Celery",
                "responses": {"200": {"description": "Service status"}},
            }
        },
    },
}

def _register_swagger(app):
    def _spec_response():
        spec = dict(OPENAPI_SPEC)
        spec["servers"] = [
            {
                "url": "/",
                "description": "Current origin",
            }
        ]
        return jsonify(spec)

    @app.route("/api/v1/openapi.json")
    @limiter.exempt
    def openapi_json_v1():
        return _spec_response()

    @app.route("/api/openapi.json")
    @limiter.exempt
    def openapi_json_legacy():
        return _spec_response()

    @app.route("/api/v1/docs")
    @limiter.exempt
    def swagger_ui_v1():
        return render_template_string(
            SWAGGER_UI_HTML,
            spec_url="/api/v1/openapi.json",
        )

    @app.route("/api/docs")
    @limiter.exempt
    def swagger_ui_legacy():
        return render_template_string(
            SWAGGER_UI_HTML,
            spec_url="/api/v1/openapi.json",
        )

def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    CORS(app, supports_credentials=True, origins=["http://localhost", "http://127.0.0.1",
                                                   "http://localhost:8080", "http://localhost:3000"])
    limiter.init_app(app)
    init_db()
    logger.info("Database initialized")
    from app.routes import bp
    app.register_blueprint(bp)
    _register_swagger(app)
    return app
