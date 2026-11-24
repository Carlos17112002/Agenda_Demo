import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

class ChangePasswordScreen extends StatefulWidget {
  const ChangePasswordScreen({super.key, this.voluntary = false});

  final bool voluntary;

  @override
  State<ChangePasswordScreen> createState() => _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends State<ChangePasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final changed = await context.read<AppState>().changePassword(
      currentPassword: _current.text,
      newPassword: _next.text,
    );
    if (!changed || !mounted || !widget.voluntary) return;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: context.palette.surface,
        title: const Text('Contraseña actualizada'),
        content: const Text('Tu nueva contraseña ya está activa.'),
        actions: [
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Listo'),
          ),
        ],
      ),
    );
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    return Scaffold(
      appBar: widget.voluntary
          ? AppBar(title: const Text('Cambiar contraseña'))
          : null,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (!widget.voluntary) const AppLogo(),
                    const SizedBox(height: 28),
                    Text(
                      widget.voluntary
                          ? 'CAMBIAR CONTRASEÑA'
                          : 'CAMBIA TU CONTRASEÑA',
                      style: const TextStyle(
                        fontSize: 26,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.8,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      widget.voluntary
                          ? 'Actualiza tu contraseña de acceso.'
                          : 'Usaste una clave temporal. Define una contraseña propia para continuar.',
                      style: TextStyle(
                        color: context.palette.muted,
                        fontSize: 13,
                        height: 1.45,
                      ),
                    ),
                    const SizedBox(height: 24),
                    if (app.errorMessage != null) ...[
                      ErrorNote(app.errorMessage!),
                      const SizedBox(height: 16),
                    ],
                    TextFormField(
                      controller: _current,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: 'Contraseña actual',
                        prefixIcon: Icon(Icons.lock_outline, size: 20),
                      ),
                      validator: (value) => (value == null || value.isEmpty)
                          ? 'Ingresa tu contraseña actual'
                          : null,
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _next,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: 'Nueva contraseña',
                        prefixIcon: Icon(Icons.lock_reset, size: 20),
                      ),
                      validator: (value) => (value == null || value.length < 12)
                          ? 'Usa al menos 12 caracteres'
                          : null,
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _confirm,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: 'Repetir contraseña',
                        prefixIcon: Icon(Icons.lock_reset, size: 20),
                      ),
                      validator: (value) =>
                          value != _next.text ? 'Las contraseñas no coinciden' : null,
                    ),
                    const SizedBox(height: 22),
                    FilledButton(
                      onPressed: app.busy ? null : _submit,
                      child: app.busy
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('ACTUALIZAR CONTRASEÑA'),
                    ),
                    const SizedBox(height: 12),
                    if (!widget.voluntary)
                      TextButton(
                        onPressed: app.busy ? null : () => app.logout(),
                        child: const Text('Cerrar sesión'),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
