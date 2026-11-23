import { act, renderHook } from '@testing-library/react';
import { describe, expect, test } from 'vitest';

import { useOnlineStatus } from './useOnlineStatus';

describe('useOnlineStatus', () => {
  test('reacciona a los eventos del navegador', () => {
    const { result } = renderHook(() => useOnlineStatus());
    expect(result.current).toBe(true);

    act(() => window.dispatchEvent(new Event('offline')));
    expect(result.current).toBe(false);

    act(() => window.dispatchEvent(new Event('online')));
    expect(result.current).toBe(true);
  });
});
