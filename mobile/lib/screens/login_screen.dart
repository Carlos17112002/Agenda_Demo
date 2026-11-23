import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _baseUrl = TextEditingController(text: 'http://127.0.0.1:8000');
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() {
    _baseUrl.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    await context.read<AppState>().login(
      baseUrl: _baseUrl.text,
      email: _email.text,
      password: _password.text,
    );
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final secondary = Theme.of(context).colorScheme.secondary;
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: RadialGradient(
            center: const Alignment(-0.7, -0.9),
            radius: 1.5,
            colors: [
              secondary.withValues(alpha: 0.2),
              context.palette.background,
            ],
            stops: const [0, 0.65],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const AppLogo(),
                      const SizedBox(height: 44),
                      const Text(
                        'CONTROLA\nTU OPERACIÓN',
                        style: TextStyle(
                          fontSize: 40,
                          height: 0.98,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -1.6,
                        ),
                      ),
                      const SizedBox(height: 14),
                      Text(
                        'Agenda, inventario y notificaciones en el bolsillo del equipo.',
                        style: TextStyle(
                          color: context.palette.muted,
                          fontSize: 14,
                          height: 1.45,
                        ),
                      ),
                      const SizedBox(height: 34),
                      if (app.errorMessage != null) ...[
                        ErrorNote(app.errorMessage!),
                        const SizedBox(height: 16),
                      ],
                      TextFormField(
                        controller: _baseUrl,
                        keyboardType: TextInputType.url,
                        decoration: const InputDecoration(
                          labelText: 'Servidor',
                          hintText: 'http://127.0.0.1:8000',
                          prefixIcon: Icon(Icons.dns_rounded, size: 20),
                        ),
                        validator: (value) =>
                            (value == null || value.trim().isEmpty)
                            ? 'Indica la URL del servidor'
                            : null,
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const [AutofillHints.email],
                        decoration: const InputDecoration(
                          labelText: 'Correo',
                          prefixIcon: Icon(Icons.alternate_email, size: 20),
                        ),
                        validator: (value) =>
                            (value == null || !value.contains('@'))
                            ? 'Ingresa un correo válido'
                            : null,
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _password,
                        obscureText: _obscure,
                        autofillHints: const [AutofillHints.password],
                        onFieldSubmitted: (_) => _submit(),
                        decoration: InputDecoration(
                          labelText: 'Contraseña',
                          prefixIcon: const Icon(Icons.lock_outline, size: 20),
                          suffixIcon: IconButton(
                            onPressed: () =>
                                setState(() => _obscure = !_obscure),
                            icon: Icon(
                              _obscure
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                              size: 20,
                            ),
                          ),
                        ),
                        validator: (value) => (value == null || value.isEmpty)
                            ? 'Ingresa tu contraseña'
                            : null,
                      ),
                      const SizedBox(height: 22),
                      FilledButton(
                        onPressed: app.busy ? null : _submit,
                        child: app.busy
                            ? SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Theme.of(
                                    context,
                                  ).colorScheme.onPrimary,
                                ),
                              )
                            : const Text('ENTRAR'),
                      ),
                      const SizedBox(height: 26),
                      Row(
                        children: [
                          const Expanded(child: Divider()),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            child: Text(
                              'SAAS MULTIEMPRESA',
                              style: TextStyle(
                                color: context.palette.muted,
                                fontSize: 9.5,
                                letterSpacing: 2,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          const Expanded(child: Divider()),
                        ],
                      ),
                      const SizedBox(height: 18),
                      Text(
                        'Cada empresa ve únicamente sus datos. Los permisos se validan en el servidor y los cambios sin conexión se sincronizan al volver.',
                        style: TextStyle(
                          color: context.palette.muted,
                          fontSize: 11.5,
                          height: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
