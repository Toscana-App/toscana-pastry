import { axe, toHaveNoViolations } from 'jest-axe';
expect.extend(toHaveNoViolations);

export async function checkAccessibility(container: HTMLElement) {
  const results = await axe(container);
  return results;
}