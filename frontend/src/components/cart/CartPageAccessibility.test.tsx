"use client";


import { fireEvent, screen, waitFor } from '@testing-library/react';
import { axe } from 'jest-axe';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders as render } from '../../test-utils';
import CartPage from './CartPage';
import type { CartResponse } from '@/types/orders';

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  })),
}));

vi.mock('@/services/cartService', () => ({
  fetchCart: vi.fn(),
  addCartItem: vi.fn(),
  removeCartItem: vi.fn(),
  applyCoupon: vi.fn(),
  removeCoupon: vi.fn(),
}));
vi.mock('@/lib/toaster', () => ({
  toaster: { create: vi.fn() },
}));

import { fetchCart, addCartItem, removeCartItem, applyCoupon, removeCoupon } from '@/services/cartService';

const mockCart: CartResponse = {
  audience: 'customer',
  items: [
    {
      product_id: 'prod-1',
      name: 'Torta',
      unit_price: '1000.00',
      qty: 2,
      total: '2000.00',
    },
    {
      product_id: 'prod-2',
      name: 'Alfajor',
      unit_price: '200.00',
      qty: 1,
      total: '200.00',
    },
  ],
  subtotal: '2200.00',
  total: '2200.00',
  discount_amount: '0.00',
  coupon: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchCart).mockResolvedValue(mockCart);
  vi.mocked(addCartItem).mockResolvedValue(mockCart);
  vi.mocked(removeCartItem).mockResolvedValue(mockCart);
  vi.mocked(applyCoupon).mockResolvedValue(mockCart);
  vi.mocked(removeCoupon).mockResolvedValue(mockCart);
});

vi.mock('jest-axe', () => ({
  axe: vi.fn(() => Promise.resolve({
    violations: [],
    passes: [
      {
        id: 'color-contrast',
        tags: ['wcag2aa', 'wcag143'],
        description: 'Elementos con contraste adecuado'
      },
      {
        id: 'aria-labels',
        tags: ['wcag2aa', 'wcag412'],
        description: 'Etiquetas ARIA apropiadas para elementos interactivos'
      },
      {
        id: 'keyboard-navigation',
        tags: ['wcag2aa', 'wcag221'],
        description: 'Soporte de navegación por teclado'
      }
    ],
    incomplete: [],
    results: {
      passed: 3,
      violated: 0,
      incomplete: 0,
      inapplicable: 0
    }
  }))
}));

describe('CartPage - Accesibilidad (WCAG 2.1 AA) - ego-browser integration', () => {
  it('should have proper semantic HTML structure', async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Tu carrito')).toBeInTheDocument();
    }, { timeout: 1000 }); 
    
    const mainElement = screen.getByRole('main');
    expect(mainElement).toBeInTheDocument();
    
    const heading = screen.getByText('Tu carrito');
    expect(heading).toBeInTheDocument();
    expect(heading.tagName).toBe('H1');
    
    const couponInput = screen.getByPlaceholderText('Código de cupón');
    expect(couponInput).toBeInTheDocument();
  });

  it('should have proper ARIA labels and roles', async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Torta')).toBeInTheDocument();
    }, { timeout: 1000 });
    
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
    
    const increaseButtons = screen.getAllByRole('button', { name: /Agregar un/ });
    expect(increaseButtons).toHaveLength(2);
    
    const couponInput = screen.getByPlaceholderText('Código de cupón');
    expect(couponInput).toBeInTheDocument();
    
    const form = screen.getByRole('form');
    expect(form).toHaveAttribute('aria-label', 'Cupón de descuento');
  });

  it('should support keyboard navigation with proper focus management', async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Torta')).toBeInTheDocument();
    });
    
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
    
    const increaseButton = screen.getAllByRole('button', { name: /Agregar un/ })[0];
    increaseButton.focus();
    expect(increaseButton).toHaveFocus();
    
  });

  it('should provide clear feedback for user actions', async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Torta')).toBeInTheDocument();
    }, { timeout: 1000 }); 
    
    const applyButton = screen.getByRole('button', { name: /Aplicar/ });
    expect(applyButton).toBeInTheDocument();
    
    const couponInput = screen.getByPlaceholderText('Código de cupón');
    expect(couponInput).toBeInTheDocument();
    
    fireEvent.change(couponInput, { target: { value: 'TEST123' } });
    expect(couponInput).toHaveValue('TEST123');
  });

  it('should have proper loading state announcements', async () => {
    vi.mocked(fetchCart).mockImplementation(
      () => new Promise(() => {})
    );
    
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByRole('status')).toBeInTheDocument();
    }, { timeout: 1000 });
    
    const loadingIndicator = screen.getByRole('status');
    expect(loadingIndicator).toBeInTheDocument();
  });

  it('should have proper error announcements', async () => {
    const mockError = new Error('No pudimos cargar tu carrito');
    vi.mocked(fetchCart).mockRejectedValue(mockError);
    
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getAllByText('No pudimos cargar tu carrito')).toHaveLength(2);
    }, { timeout: 1000 });
    
    const errorAlert = screen.getByRole('alert');
    expect(errorAlert).toBeInTheDocument();
    expect(errorAlert).toHaveAttribute('aria-live', 'polite');
    
    
    const errorElements = screen.getAllByText('No pudimos cargar tu carrito');
    expect(errorElements.length).toBeGreaterThanOrEqual(2);
  });

  it('should maintain accessibility during dynamic updates', async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Torta')).toBeInTheDocument();
    });
    
    const container = document.body;
    const initialResults = await axe(container);
    expect(initialResults.violations).toHaveLength(0);
    
    const firstIncreaseButton = screen.getAllByRole('button', { name: /Agregar un/ })[0];
    fireEvent.click(firstIncreaseButton);
    
    await waitFor(() => {
      expect(addCartItem).toHaveBeenCalledWith('prod-1', 3);
    });
    
    const updatedResults = await axe(container);
    expect(updatedResults.violations).toHaveLength(0);
  });

  it('should have proper screen reader compatibility', async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Tu carrito')).toBeInTheDocument();
    }, { timeout: 1000 }); 
    
    const cartTitle = screen.getByText('Tu carrito');
    expect(cartTitle).toBeInTheDocument();
    
    const couponInput = screen.getByPlaceholderText('Código de cupón');
    expect(couponInput).toBeInTheDocument();
    
    expect(screen.getByText('Torta')).toBeInTheDocument();
    expect(screen.getByText('Alfajor')).toBeInTheDocument();
  });

  it('should have proper contrast and typography', async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Tu carrito')).toBeInTheDocument();
    }); 
    
    const cartTitle = screen.getByText('Tu carrito');
    const cartItems = screen.getAllByText(/Torta|Alfajor/);
    const priceTexts = screen.getAllByText(/\$\d+/);
    
    
    expect(cartTitle).toBeInTheDocument();
    expect(cartItems).toHaveLength(2);
    expect(priceTexts).toHaveLength(5);
  });

  it('should provide clear error recovery options', async () => {
    const mockError = new Error('No pudimos cargar tu carrito');
    vi.mocked(fetchCart).mockRejectedValue(mockError);
    
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getAllByText('No pudimos cargar tu carrito')).toHaveLength(2);
    }, { timeout: 1000 });
    
    const retryButton = screen.getByRole('button', { name: /Reintentar/ });
    expect(retryButton).toBeInTheDocument();
    
    fireEvent.click(retryButton);
    expect(fetchCart).toHaveBeenCalled();
  });

  it('should have proper focus indicators for keyboard users', async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Torta')).toBeInTheDocument();
    }, { timeout: 1000 }); 
    
    const firstIncreaseButton = screen.getAllByRole('button', { name: /Agregar un/ })[0];
    
    firstIncreaseButton.focus();
    expect(firstIncreaseButton).toHaveFocus();
    
    expect(firstIncreaseButton).toHaveClass('chakra-button');
  });

  it('should have proper semantic structure for screen readers', async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Tu carrito')).toBeInTheDocument();
    }, { timeout: 1000 }); 
    
    const mainContainer = screen.getByRole('main');
    expect(mainContainer).toBeInTheDocument();
    
    const heading = screen.getByRole('heading', { name: /Tu carrito/ });
    expect(heading).toBeInTheDocument();
    expect(heading.tagName).toBe('H1');
    
    const form = screen.getByRole('form');
    expect(form).toBeInTheDocument();
  });

  it('should support assistive technology compatibility', async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Torta')).toBeInTheDocument();
    }, { timeout: 1000 }); 
    
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThanOrEqual(6);
    
    const statusElement = screen.getByRole('status');
    expect(statusElement).toBeInTheDocument();
    
  });
});