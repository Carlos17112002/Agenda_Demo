import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue, makeCompany } from '../../test/factories';
import { CompanyChooserPage } from './CompanyChooserPage';

describe('CompanyChooserPage', () => {
  test('muestra las empresas y activa la elegida', async () => {
    const selectCompany = vi.fn().mockResolvedValue(undefined);
    const auth = makeAuthValue({
      status: 'choosingCompany',
      companies: [
        makeCompany({ id: 'company-a', display_name: 'Estudio Aurora' }),
        makeCompany({ id: 'company-b', display_name: 'Marca Demo Visual' }),
      ],
      selectCompany,
    });

    render(
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={['/empresa']}>
          <Routes>
            <Route path="/empresa" element={<CompanyChooserPage />} />
            <Route path="/agenda" element={<p>Agenda cargada</p>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    );

    await userEvent.click(screen.getByRole('button', { name: /Marca Demo Visual/ }));

    expect(selectCompany).toHaveBeenCalledWith(expect.objectContaining({ id: 'company-b' }));
    expect(await screen.findByText('Agenda cargada')).toBeInTheDocument();
  });
});
