import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/branding.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'create_company_screen.dart';

class CompanyScreen extends StatelessWidget {
  const CompanyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    return Scaffold(
      appBar: AppBar(
        title: const AppLogo(compact: true),
        actions: [
          IconButton(
            tooltip: 'Cerrar sesión',
            onPressed: app.busy ? null : app.logout,
            icon: const Icon(Icons.logout_rounded),
          ),
        ],
      ),
      body: Stack(
        children: [
          ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 40),
            children: [
              const SizedBox(height: 12),
              const Text(
                'ELIGE EMPRESA',
                style: TextStyle(
                  fontSize: 30,
                  fontWeight: FontWeight.w900,
                  letterSpacing: -0.8,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Solo verás la agenda, inventario y notificaciones de la empresa activa.',
                style: TextStyle(color: context.palette.muted, height: 1.4),
              ),
              const SizedBox(height: 28),
              if (app.errorMessage != null) ...[
                ErrorNote(app.errorMessage!),
                const SizedBox(height: 16),
              ],
              if (app.isSaasAdmin) ...[
                SurfaceCard(
                  key: const Key('create-company-open'),
                  onTap: app.busy
                      ? null
                      : () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const CreateCompanyScreen(),
                          ),
                        ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.add_business_rounded,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Crear empresa',
                              style: TextStyle(
                                fontWeight: FontWeight.w800,
                                fontSize: 15,
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              'Alta asistida para clientes que llaman por teléfono.',
                              style: TextStyle(
                                color: context.palette.muted,
                                fontSize: 12,
                                height: 1.35,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Icon(
                        Icons.arrow_forward_ios_rounded,
                        size: 16,
                        color: context.palette.muted,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],
              for (final company in app.companies)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: SurfaceCard(
                    onTap: app.busy
                        ? null
                        : () => context.read<AppState>().selectCompany(company),
                    child: Row(
                      children: [
                        CompanyLogo(company: company),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                Branding.fromCompany(company).displayName,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                  fontSize: 16,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${company['slug'] ?? ''} · ${company['status'] ?? ''}',
                                style: TextStyle(
                                  color: context.palette.muted,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Icon(
                          Icons.arrow_forward_ios_rounded,
                          size: 16,
                          color: context.palette.muted,
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
          if (app.busy)
            Container(
              color: context.palette.background.withValues(alpha: 0.55),
              alignment: Alignment.center,
              child: const CircularProgressIndicator(),
            ),
        ],
      ),
    );
  }
}
