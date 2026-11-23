import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'core/branding.dart';
import 'core/theme.dart';
import 'screens/change_password_screen.dart';
import 'screens/company_screen.dart';
import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'state/app_state.dart';
import 'widgets/common.dart';

class AgendaApp extends StatefulWidget {
  const AgendaApp({super.key, this.state});

  final AppState? state;

  @override
  State<AgendaApp> createState() => _AgendaAppState();
}

class _AgendaAppState extends State<AgendaApp> {
  late final AppState _state = widget.state ?? AppState();

  @override
  void initState() {
    super.initState();
    if (widget.state == null) {
      _state.bootstrapApp();
    }
  }

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: _state,
      child: Consumer<AppState>(
        builder: (context, app, _) {
          final branding = app.bootstrap?.branding ?? Branding.fallback;
          return MaterialApp(
            title: branding.displayName,
            debugShowCheckedModeBanner: false,
            theme: buildAgendaTheme(branding),
            locale: const Locale('es'),
            supportedLocales: const [Locale('es')],
            localizationsDelegates: GlobalMaterialLocalizations.delegates,
            home: const _RootGate(),
          );
        },
      ),
    );
  }
}

class _RootGate extends StatelessWidget {
  const _RootGate();

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    return switch (app.status) {
      AppStatus.loading => const _Splash(),
      AppStatus.loggedOut => const LoginScreen(),
      AppStatus.chooseCompany => const CompanyScreen(),
      AppStatus.failure => _FailureScreen(message: app.errorMessage),
      AppStatus.ready => app.bootstrap?.mustChangePassword == true
          ? const ChangePasswordScreen()
          : const HomeShell(),
    };
  }
}

class _Splash extends StatelessWidget {
  const _Splash();

  @override
  Widget build(BuildContext context) {
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
        child: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              AppLogo(),
              SizedBox(height: 28),
              SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FailureScreen extends StatelessWidget {
  const _FailureScreen({this.message});

  final String? message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.cloud_off_rounded,
                  size: 48,
                  color: Theme.of(context).colorScheme.error,
                ),
                const SizedBox(height: 18),
                const Text(
                  'No pudimos conectar',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 10),
                Text(
                  message ?? 'Revisa tu conexión e inténtalo nuevamente.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: context.palette.muted,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: () => context.read<AppState>().bootstrapApp(),
                  child: const Text('Reintentar'),
                ),
                const SizedBox(height: 10),
                TextButton(
                  onPressed: () => context.read<AppState>().logout(),
                  child: const Text('Volver al inicio de sesión'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
