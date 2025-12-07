# Frontend Architecture

## Overview

Type-safe React application with Next.js 15, connecting to FastAPI backend via custom API client and React hooks.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js 15)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────┐      │
│  │              React Components (Pages/UI)               │      │
│  │  • WorkerSearchPage  • EstimateForm  • PaymentButton  │      │
│  └───────────────┬───────────────────────────────────────┘      │
│                  │ uses                                          │
│                  ▼                                               │
│  ┌───────────────────────────────────────────────────────┐      │
│  │              React Hooks (lib/hooks/)                  │      │
│  │  • useWorkerSearch  • useEstimate  • usePayment       │      │
│  │                                                        │      │
│  │  Responsibilities:                                     │      │
│  │  - State management (loading, error, data)            │      │
│  │  - Automatic polling for async operations             │      │
│  │  - Error handling and transformation                  │      │
│  └───────────────┬───────────────────────────────────────┘      │
│                  │ calls                                         │
│                  ▼                                               │
│  ┌───────────────────────────────────────────────────────┐      │
│  │             API Services (lib/api/)                    │      │
│  │  • workersApi  • paymentsApi  • estimatesApi          │      │
│  │                                                        │      │
│  │  Responsibilities:                                     │      │
│  │  - Domain-specific endpoint organization              │      │
│  │  - Request/response type safety                       │      │
│  └───────────────┬───────────────────────────────────────┘      │
│                  │ uses                                          │
│                  ▼                                               │
│  ┌───────────────────────────────────────────────────────┐      │
│  │             API Client (lib/api/client.ts)             │      │
│  │                                                        │      │
│  │  Responsibilities:                                     │      │
│  │  - HTTP request/response handling                     │      │
│  │  - JSON parsing and error transformation              │      │
│  │  - Consistent ApiResponse<T> wrapper                  │      │
│  │  - Base URL and header management                     │      │
│  └───────────────┬───────────────────────────────────────┘      │
│                  │                                               │
│                  │ HTTP/JSON                                     │
└──────────────────┼───────────────────────────────────────────────┘
                   │
                   │ CORS-enabled requests
                   │
┌──────────────────▼───────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────┐      │
│  │                  API Routes (app/routes/)              │      │
│  │  • workers_search.py  • payments.py  • estimates.py   │      │
│  └───────────────┬───────────────────────────────────────┘      │
│                  │ validates with                                │
│                  ▼                                               │
│  ┌───────────────────────────────────────────────────────┐      │
│  │              Pydantic Schemas (app/schemas/)           │      │
│  │  • worker.py  • payment.py  • estimate.py             │      │
│  │                                                        │      │
│  │  Source of Truth for Types                            │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

## Data Flow Example: Worker Search

```
1. User clicks "Search Workers"
   └─> Component calls: search({ project_type: "pool", location: "Canggu" })

2. useWorkerSearch hook
   ├─> Sets loading = true
   ├─> Clears previous error
   └─> Calls: workersApi.search(request)

3. workersApi.search()
   ├─> Validates types at compile time
   └─> Calls: apiClient.post<WorkerSearchResponse>("/workers/search", request)

4. apiClient.post()
   ├─> Adds base URL: http://localhost:8000
   ├─> Sets headers: Content-Type: application/json
   ├─> Sends: POST http://localhost:8000/workers/search
   └─> Receives: JSON response

5. Response handling
   ├─> Success: { data: WorkerSearchResponse }
   └─> Error: { error: { message, code, details } }

6. Hook updates state
   ├─> Sets loading = false
   ├─> Sets data = response.data (if success)
   └─> Sets error = response.error.message (if error)

7. Component re-renders
   └─> Displays workers or error message
```

## Type Safety Flow

```
Backend (Python)                    Frontend (TypeScript)
─────────────────                   ──────────────────────

class WorkerPreview(BaseModel):     interface WorkerPreview {
    id: str                             id: string
    preview_name: str          →        preview_name: string
    trust_score: TrustScore                trust_score: TrustScoreDetailed
    location: str                       location: string
    ...                                 ...
}                                   }

Pydantic validates at runtime       TypeScript validates at compile time
Backend rejects invalid requests    Frontend prevents invalid requests
```

## Module Responsibilities

### Components (`app/`)
**What**: UI and user interactions
**Example**: `<WorkerSearchPage />`, `<EstimateForm />`
**Knows about**: Hooks, types, user input
**Doesn't know**: API endpoints, HTTP details

### Hooks (`lib/hooks/`)
**What**: State management and business logic
**Example**: `useWorkerSearch()`, `useEstimate()`
**Knows about**: API services, state updates, polling logic
**Doesn't know**: HTTP details, URL construction

### API Services (`lib/api/`)
**What**: Domain-specific endpoint organization
**Example**: `workersApi.search()`, `paymentsApi.unlockWorker()`
**Knows about**: Endpoints, request/response types, API client
**Doesn't know**: Component state, UI logic

### API Client (`lib/api/client.ts`)
**What**: Low-level HTTP communication
**Example**: `apiClient.post<T, B>(endpoint, body)`
**Knows about**: HTTP methods, headers, error handling
**Doesn't know**: Business logic, specific endpoints

### Types (`lib/types/`)
**What**: TypeScript type definitions
**Example**: `WorkerPreview`, `EstimateResponse`
**Knows about**: Backend schema structure
**Doesn't know**: How data is fetched or used

## Configuration

### Environment Variables
```
NEXT_PUBLIC_API_URL        → API base URL
NEXT_PUBLIC_MIDTRANS_*     → Payment gateway config
NEXT_PUBLIC_APP_URL        → Frontend URL for callbacks
NEXT_PUBLIC_ENVIRONMENT    → dev/staging/production
```

### Config Module (`lib/config.ts`)
```typescript
export const config = {
  api: { baseURL: process.env.NEXT_PUBLIC_API_URL },
  midtrans: { clientKey: process.env.NEXT_PUBLIC_MIDTRANS_CLIENT_KEY },
  app: { url: process.env.NEXT_PUBLIC_APP_URL, environment: "..." }
}
```

## Error Handling Strategy

### Three-Layer Error Handling

**Layer 1: API Client**
- Catches network errors
- Parses HTTP errors
- Transforms to `ApiError` format

**Layer 2: Hooks**
- Receives `ApiResponse<T>`
- Extracts error message
- Updates component-friendly error state

**Layer 3: Components**
- Displays user-friendly error messages
- Provides retry actions
- Logs to monitoring (future)

### Error Flow Example
```
Network Error
    ↓
API Client: { error: { message: "Network error", code: "NETWORK_ERROR" } }
    ↓
Hook: setError("Network error")
    ↓
Component: <ErrorMessage>Network error</ErrorMessage>
```

## Async Operation Patterns

### Pattern 1: Fire and Forget (Worker Search)
```typescript
const { search } = useWorkerSearch();
await search(request);
// Done - results available immediately
```

### Pattern 2: Polling (Cost Estimate)
```typescript
const { createEstimate, progress } = useEstimate();
await createEstimate(request);
// Hook polls backend until status = "completed"
// progress: 0 → 25 → 50 → 75 → 100
```

### Pattern 3: Redirect (Payment)
```typescript
const { initiateUnlock } = usePayment();
await initiateUnlock(workerId, PaymentMethod.GOPAY);
// Automatically redirects to payment gateway
```

## Caching Strategy (Future)

**Current**: No caching (always fetch fresh)

**Planned**:
- React Query for automatic caching
- Stale-while-revalidate pattern
- Optimistic updates for instant UX

## Testing Strategy

### Unit Tests
- Test API client error handling
- Test hook state transitions
- Mock fetch calls

### Integration Tests
- Test full request/response cycle
- Test polling behavior
- Test error scenarios

### E2E Tests
- Test user flows with real backend
- Test payment integration
- Test worker search to unlock flow

## Performance Considerations

### Current Optimizations
- JSON parsing only when needed
- Automatic request deduplication via React
- Polling timeout (60s max)

### Future Optimizations
- Request caching with React Query
- Request cancellation on unmount
- Debounced search inputs
- Virtualized lists for large datasets
- Service worker for offline support

## Security Considerations

### Client-Side
- No sensitive keys in frontend code
- Midtrans client key only (server key on backend)
- HTTPS only in production
- Input validation before API calls

### API Communication
- CORS validation on backend
- Rate limiting on backend
- HTTPS encryption in production
- XSS prevention via React (auto-escaping)

## Deployment

### Development
```bash
npm run dev          # localhost:3000
```

### Production Build
```bash
npm run build        # Creates optimized build
npm start            # Serves production build
```

### Environment-Specific Config
- Development: `http://localhost:8000`
- Staging: `https://api-staging.yourdomain.com`
- Production: `https://api.yourdomain.com`

## File Organization

```
frontend/
├── app/                    # Next.js pages and routes
│   ├── page.tsx           # Homepage
│   ├── layout.tsx         # Root layout
│   └── test-api/          # API test page
├── lib/                   # Core application logic
│   ├── api/               # API client and services
│   ├── hooks/             # React hooks
│   ├── types/             # TypeScript types
│   └── config.ts          # Configuration
├── .env.local             # Environment variables (gitignored)
├── .env.local.example     # Environment template
├── INTEGRATION.md         # Integration documentation
├── QUICKSTART.md          # Quick reference guide
└── ARCHITECTURE.md        # This file
```

## Key Design Principles

1. **Single Responsibility**: Each module has one clear purpose
2. **Type Safety**: TypeScript everywhere, matching backend schemas
3. **Error Handling**: Explicit error states, no silent failures
4. **Developer Experience**: Clear APIs, helpful error messages, good docs
5. **Maintainability**: Organized structure, consistent patterns, comments
