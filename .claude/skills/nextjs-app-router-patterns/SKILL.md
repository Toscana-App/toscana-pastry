---
name: nextjs-app-router-patterns
description: Master Next.js 14+ App Router with Server Components, streaming, parallel routes, and advanced data fetching. Use when building Next.js applications, implementing SSR/SSG, or optimizing React Server Components.
---

# Next.js App Router Patterns

Comprehensive patterns for Next.js 14+ App Router architecture, Server Components, and modern full-stack React development.

## When to Use This Skill

- Building new Next.js applications with App Router
- Migrating from Pages Router to App Router
- Implementing Server Components and streaming
- Setting up parallel and intercepting routes
- Optimizing data fetching and caching
- Building full-stack features with Server Actions

## Core Concepts

### 1. Rendering Modes

| Mode                  | Where        | When to Use                               |
| --------------------- | ------------ | ----------------------------------------- |
| **Server Components** | Server only  | Data fetching, heavy computation, secrets |
| **Client Components** | Browser      | Interactivity, hooks, browser APIs        |
| **Static**            | Build time   | Content that rarely changes               |
| **Dynamic**           | Request time | Personalized or real-time data            |
| **Streaming**         | Progressive  | Large pages, slow data sources            |

### 2. File Conventions

```
app/
├── layout.tsx       # Shared UI wrapper
├── page.tsx         # Route UI
├── loading.tsx      # Loading UI (Suspense)
├── error.tsx        # Error boundary
├── not-found.tsx    # 404 UI
├── route.ts         # API endpoint
├── template.tsx     # Re-mounted layout
├── default.tsx      # Parallel route fallback
└── opengraph-image.tsx  # OG image generation
```

### 3. Route guards: `proxy.ts` (Next 16) / `middleware.ts` (≤15)

Next 16 renamed the convention: the file is `proxy.ts` and the exported function is `proxy`. The old name still runs but warns on every build (`npx @next/codemod@canary middleware-to-proxy .`).

A guard has two independent halves — `matcher` decides **whether** the guard runs, the function body decides **what it protects**. A path listed in `matcher` with no matching predicate in the body is silently unprotected; nothing warns you about it.

```typescript
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const PROTECTED_PREFIXES = ['/dashboard', '/profile']

export function proxy(request: NextRequest) {
  const token = request.cookies.get('auth_token')?.value
  const { pathname } = request.nextUrl

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  )

  if (isProtected && !token) {
    const url = new URL('/login', request.url)
    url.searchParams.set('from', pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = { matcher: ['/dashboard/:path*', '/profile/:path*'] }
```

- Derive both halves from one `PROTECTED_PREFIXES` constant so matcher and body cannot drift apart.
- Match with `pathname === prefix || pathname.startsWith(prefix + '/')`. A bare `startsWith(prefix)` also matches `/profilex`, and `/segment/:path*` in a matcher does match `/segment` itself.
- The guard reads the cookie from the **request**, so a token written by client-side JS is only visible to navigations that happen after it is set. Anything that must be protected on the very first request needs the cookie set server-side.
- Client-set cookies need `path=/` and `SameSite=Lax`, or the guard sees nothing.
- Passing `from` in the redirect query lets the login page return the user to where they were headed.

### 4. `params` and `searchParams` are Promises (15+)

```typescript
// app/orders/[id]/page.tsx — server component
import { OrderDetail } from '@/components/orders/order-detail'

export default async function OrderPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params      // await in the SERVER component...
  return <OrderDetail id={id} />   // ...and pass plain values, never the Promise
}
```

- A Promise is not serializable: passing `params` itself down to a client component fails at the server→client boundary. Await it on the server and pass the resolved values.
- The same shape applies to `searchParams`, `generateMetadata`, and route handlers (`{ params }: { params: Promise<{ id: string }> }`).
- Awaiting `params` does not make the page dynamic by itself — a page can stay static and still await it.

### 5. One guard and one shell per section, in the section layout

Put the access guard, the page container and the section navigation in `app/<section>/layout.tsx`, and let each `page.tsx` render only its content.

- A guard repeated per page is N chances to forget it: a route added under the section later is unprotected by default, while a layout covers every route under it, including ones written after it.
- The layout also owns the section `metadata` (`title: { default, template }`), so page metadata only carries its own title.
- Keep the layout a server component and let the pages under it be client components: the guard and the chrome stay server-side, the interactive surface stays client-side.
- Don't double-guard: once the layout guards, remove the guard wrapper from the pages it covers.

## Quick Start

```typescript
// app/layout.tsx
import { Inter } from 'next/font/google'
import { Providers } from './providers'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  title: { default: 'My App', template: '%s | My App' },
  description: 'Built with Next.js App Router',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}

// app/page.tsx - Server Component by default
async function getProducts() {
  const res = await fetch('https://api.example.com/products', {
    next: { revalidate: 3600 }, // ISR: revalidate every hour
  })
  return res.json()
}

export default async function HomePage() {
  const products = await getProducts()

  return (
    <main>
      <h1>Products</h1>
      <ProductGrid products={products} />
    </main>
  )
}
```

## Detailed patterns and worked examples

Detailed pattern documentation lives in `references/details.md`. Read that file when the navigation tier above is insufficient.

## Best Practices

### Do's

- **Start with Server Components** - Add 'use client' only when needed
- **Colocate data fetching** - Fetch data where it's used
- **Use Suspense boundaries** - Enable streaming for slow data
- **Leverage parallel routes** - Independent loading states
- **Use Server Actions** - For mutations with progressive enhancement

### Don'ts

- **Don't pass serializable data** - Server → Client boundary limitations
- **Don't use hooks in Server Components** - No useState, useEffect
- **Don't fetch in Client Components** - Use Server Components or React Query
- **Don't over-nest layouts** - Each layout adds to the component tree
- **Don't ignore loading states** - Always provide loading.tsx or Suspense
