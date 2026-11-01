import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const PROTECTED_PREFIXES = [
  '/',
  '/my-orders',
  '/carrito',
  '/checkout',
  '/dashboard',
  '/profile',
  '/admin',
  '/products',
]

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

export const config = {
  // Next requires the matcher to be static (it cannot be derived from
  // PROTECTED_PREFIXES at runtime), so the two lists must stay in sync
  // MANUALLY: '/admin' was missing here, so the proxy never ran for that
  // route (the /admin guard was dead code).
  matcher: [
    '/',
    '/my-orders',
    '/my-orders/:path*',
    '/carrito',
    '/carrito/:path*',
    '/checkout',
    '/checkout/:path*',
    '/dashboard',
    '/dashboard/:path*',
    '/profile',
    '/profile/:path*',
    '/admin',
    '/admin/:path*',
    '/products',
    '/products/:path*',
  ],
}
