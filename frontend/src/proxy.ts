import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const PROTECTED_PREFIXES = ['/dashboard', '/profile', '/admin', '/products']

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
  // Next exige que el matcher sea estático (no se puede derivar de
  // PROTECTED_PREFIXES en runtime), así que las dos listas tienen que
  // mantenerse sincronizadas A MANO: acá faltaba '/admin', y con eso el
  // proxy nunca corría para esa ruta (el guard de /admin era código muerto).
  matcher: [
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
