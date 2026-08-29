# Widget Serving Architecture

## Overview

The application now uses a **separated widget file serving architecture** where:
- **Widget files** (widget.js, widget.css) are served by the **frontend** (Vite)
- **API calls** are made to the **backend** (FastAPI)
- **CORS validation** is performed on the backend for API calls

This separation improves:
- ✅ Architectural clarity (frontend serves UI assets, backend serves data)
- ✅ Scalability (widget CDN can be different from API server)
- ✅ Security (clearer isolation of concerns)
- ✅ Performance (widget can be cached at frontend CDN edge)

## How It Works

### 1. Embed Snippet Generation (Admin Dashboard)

When admin configures an application and copies the embed snippet:

**Frontend/ApplicationDetail.jsx:**
```javascript
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const FRONTEND_URL = import.meta.env.VITE_FRONTEND_URL || "http://localhost:5173";

const embedSnippet = `
<script>
  window.OceanRAGWidgetConfig = {
    widgetKey: "${widget.public_key}",
    appId: "${application.id}",
    backendUrl: "${BACKEND_URL}"  // ← Only backend URL in config
  };
</script>
<script src="${FRONTEND_URL}/widget/widget.js" async></script>  // ← Load from FRONTEND
`;
```

### 2. Client Website Integration

Client websites embed the snippet in their HTML:

```html
<!-- Client's website (e.g., example.com) -->
<script>
  window.OceanRAGWidgetConfig = {
    widgetKey: "wk_xxx",
    appId: "app_xxx",
    backendUrl: "https://api.oceanrag.com"  // Backend API domain
  };
</script>
<script src="https://app.oceanrag.com/widget/widget.js" async></script>  <!-- Frontend domain -->
```

### 3. Widget Script Execution

**Frontend/public/widget/widget.js:**
```javascript
// Extract configuration from window
const config = window.OceanRAGWidgetConfig;
const API_URL = config.backendUrl;  // ← Use only for API calls
const WIDGET_PUBLIC_KEY = config.widgetKey;

// Determine widget CSS location (relative to where this script was loaded)
const link = document.createElement("link");
link.href = new URL("widget.css", document.currentScript?.src).href;
document.head.appendChild(link);

// Make API calls to BACKEND only
fetch(`${API_URL}/api/client/widget/configuration`, {
  headers: {
    "X-Widget-Key": WIDGET_PUBLIC_KEY
  }
});

fetch(`${API_URL}/api/client/conversations/send-message`, {
  headers: {
    "X-Widget-Key": WIDGET_PUBLIC_KEY,
    "Content-Type": "application/json"
  }
});
```

### 4. CORS Validation (Backend)

**Backend/DynamicCorsMiddleware:**
```python
# Widget API routes trigger dynamic CORS middleware
# (/api/client/widget/*, /api/client/conversations/*)

# Middleware checks:
1. Extract widget key from X-Widget-Key header
2. Fetch allowed_origins from database (cached 60s)
3. Check if request Origin matches allowed_origins
4. Return appropriate CORS headers or 400 error
```

**Key Points:**
- ✅ Browser enforces CORS validation
- ✅ Backend provides CORS headers only for valid origins
- ✅ Invalid origins get 400 response from DynamicCorsMiddleware
- ✅ Empty allowed_origins list = allow all origins (development mode)

## Serving Locations

### Development

| Resource | Location | Served By | URL |
|----------|----------|-----------|-----|
| Widget JS | frontend/public/widget/widget.js | Vite dev server | http://localhost:5173/widget/widget.js |
| Widget CSS | frontend/public/widget/widget.css | Vite dev server | http://localhost:5173/widget/widget.css |
| API | backend/app/api/ | FastAPI | http://localhost:8000/api/ |
| Admin Dashboard | frontend/src/pages/ | Vite dev server | http://localhost:5173/ |

### Production

| Resource | Location | Served By | URL |
|----------|----------|-----------|-----|
| Widget JS | dist/widget/widget.js | Frontend CDN/Server | https://app.example.com/widget/widget.js |
| Widget CSS | dist/widget/widget.css | Frontend CDN/Server | https://app.example.com/widget/widget.css |
| API | production backend | FastAPI on server | https://api.example.com/api/ |
| Admin Dashboard | dist/index.html | Frontend CDN/Server | https://app.example.com/ |

## Environment Variables

### Frontend (.env)

```env
# API server URL - only used by widget for API calls
VITE_BACKEND_URL=http://localhost:8000

# Frontend server URL - used to serve widget files
# Points to where widget.js and widget.css are located
VITE_FRONTEND_URL=http://localhost:5173
```

### Development Example
```env
VITE_BACKEND_URL=http://localhost:8000
VITE_FRONTEND_URL=http://localhost:5173
```

### Production Example
```env
VITE_BACKEND_URL=https://api.example.com
VITE_FRONTEND_URL=https://app.example.com
```

### Backend (.env)

The backend **does not need** FRONTEND_URL configuration. Widget files are handled entirely by the frontend.

The backend does not serve widget files. It only serves API endpoints; widget assets are served by the frontend.

## Key Changes from Previous Architecture

### Before (Monolithic)
```
Client Website
├── widget.js from BACKEND_URL/widget/widget.js
└── API calls to BACKEND_URL/api/
    └── CORS validation on OPTIONS requests
```

### After (Separated)
```
Client Website
├── widget.js from FRONTEND_URL/widget/widget.js
└── API calls to BACKEND_URL/api/
    └── CORS validation on OPTIONS requests
```

## File Locations

### Frontend (Vite Project)
```
frontend/
├── public/widget/          ← Served as-is at /widget/ in dev and production
│   ├── widget.js
│   └── widget.css
├── src/pages/
│   └── ApplicationDetail.jsx  ← Generates embed snippets with FRONTEND_URL
└── vite.config.js          ← Configured to serve public/widget/ assets
```

### Backend
```
backend/
└── app/main.py            ← Serves API endpoints only
```

## Testing the Widget Serving

### 1. Development

```bash
# Terminal 1: Start frontend (Vite dev server)
cd frontend
npm install
npm run dev
# Vite runs at http://localhost:5173

# Terminal 2: Start backend
cd backend
python -m uvicorn app.main:app --reload
# FastAPI runs at http://localhost:8000

# In Admin Dashboard (http://localhost:5173):
# 1. Create an application with allowed origins
# 2. Copy the embed snippet
# 3. Note the widget script URL is from http://localhost:5173/widget/widget.js
# 4. Test on client website
```

### 2. Check Widget Loading

Open browser DevTools (F12) and check Network tab:
```
✅ widget.js loaded from: http://localhost:5173/widget/widget.js
✅ widget.css loaded from: http://localhost:5173/widget/widget.css
✅ /api/client/widget/configuration called to: http://localhost:8000/api/...
```

### 3. CORS Validation

The browser automatically enforces CORS:
- ✅ If request's Origin matches allowed_origins → success
- ❌ If request's Origin doesn't match → browser blocks (403)
- ✅ If allowed_origins is empty → all origins allowed (development mode)

Backend logs will show:
```
INFO: X-Widget-Key: wk_xxx | Origin: https://client.example.com | Status: 200 ✓
```

## Production Deployment

### Frontend Setup

1. **Build widget files:**
```bash
cd frontend
npm run build
# Creates dist/widget/widget.js and dist/widget/widget.css
```

2. **Deploy to production server/CDN:**
```bash
# Upload dist/ to your server
# Make sure dist/widget/ is accessible at https://app.example.com/widget/
```

3. **Set environment variables:**
```bash
# .env.production
VITE_BACKEND_URL=https://api.example.com
VITE_FRONTEND_URL=https://app.example.com
```

### Backend Setup

1. **Backend runs normally** (no changes needed for widget serving)
   
2. **Verify CORS configuration:**
```python
# backend/.env
ALLOWED_ORIGINS=https://client1.com,https://client2.com
CORS_ALLOW_LOCAL_ORIGINS=false  # Only for production
```

3. **Admin dashboard URL:** https://app.example.com/
   - Admins create applications and configure allowed_origins
   - Generated embed snippets point to https://app.example.com/widget/widget.js

## Troubleshooting

### Widget script doesn't load
```
Check:
✓ VITE_FRONTEND_URL is correct
✓ Widget files exist: frontend/public/widget/widget.js
✓ Frontend server is running and accessible
✓ CORS headers from backend are correct
```

### API calls fail with CORS error
```
Check:
✓ VITE_BACKEND_URL is correct
✓ Application has allowed_origins configured
✓ Client website Origin header matches allowed_origins
✓ DynamicCorsMiddleware is wired in main.py (before GlobalCORSMiddleware)
```

### CSS doesn't load
```
Check:
✓ Widget.js is loaded from correct URL
✓ CSS file exists at: FRONTEND_URL/widget/widget.css
✓ Relative URL resolution in widget.js works correctly
```

## Security Notes

1. **Widget Key** (`wk_xxx`)
   - Public by design (visible in page source)
   - Used only to identify the application
   - Backend resolves actual application from widget key

2. **Origin Validation**
   - Checked by browser (SOP - Same Origin Policy)
   - Validated by backend (DynamicCorsMiddleware)
   - Empty list = allow all (development/demo mode)

3. **Separation Benefits**
   - Frontend CDN can be different from backend API
   - Widget files can be cached at edge
   - Secret credentials never mixed with public widget
   - Clear security boundary between UI assets and data

## Migration from Old Architecture

If you're migrating from the previous architecture (widget from BACKEND_URL):

1. **Update ApplicationDetail.jsx** ✅ (Already done)
   - Uses FRONTEND_URL for widget script
   - Keeps BACKEND_URL for API calls

2. **Update frontend .env** ✅ (Already done)
   - Add VITE_FRONTEND_URL configuration

3. **Test widget on new URL**
   - Copy new embed snippet from admin dashboard
   - Test on client website
   - Verify widget.js loads from FRONTEND_URL

Old embed snippets using `BACKEND_URL/widget/widget.js` must be replaced because the backend no longer serves widget assets.
