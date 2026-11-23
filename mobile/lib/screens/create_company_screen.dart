import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

const _emailPattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$';
const _slugPattern = r'^[-a-zA-Z0-9_]{1,100}$';
const _reservedSlugs = {
  'admin',
  'agenda',
  'api',
  'app',
  'auth',
  'b',
  'health',
  'login',
  'media',
  'mobile',
  'public',
  'register',
  'saas',
  'static',
};

class CreateCompanyScreen extends StatefulWidget {
  const CreateCompanyScreen({super.key});

  @override
  State<CreateCompanyScreen> createState() => _CreateCompanyScreenState();
}

class _CreateCompanyScreenState extends State<CreateCompanyScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _slug = TextEditingController();
  final _email = TextEditingController();
  final _firstName = TextEditingController();
  final _trialDays = TextEditingController();
  bool _slugEdited = false;
  bool _trialEdited = false;
  String? _planCode;
  CompanyCreationResult? _result;

  @override
  void initState() {
    super.initState();
    _name.addListener(_syncSlug);
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadPlans());
  }

  @override
  void dispose() {
    _name.removeListener(_syncSlug);
    _name.dispose();
    _slug.dispose();
    _email.dispose();
    _firstName.dispose();
    _trialDays.dispose();
    super.dispose();
  }

  Future<void> _loadPlans() async {
    final app = context.read<AppState>();
    await app.loadPlans();
    if (!mounted || app.plans.isEmpty) return;
    final current = _planCode;
    if (current == null) {
      _selectPlan(
        app.plans.firstWhere((plan) => plan.isDefault, orElse: () => app.plans.first),
      );
    }
  }

  void _selectPlan(PlanOption plan) {
    setState(() => _planCode = plan.code);
    if (!_trialEdited) _trialDays.text = plan.trialDays.toString();
  }

  PlanOption? _selectedPlan(List<PlanOption> plans) {
    for (final plan in plans) {
      if (plan.code == _planCode) return plan;
    }
    return null;
  }

  void _syncSlug() {
    if (_slugEdited) return;
    final slug = _slugify(_name.text);
    if (_slug.text == slug) return;
    _slug.value = TextEditingValue(
      text: slug,
      selection: TextSelection.collapsed(offset: slug.length),
    );
  }

  static String _slugify(String input) {
    const source = 'áàäâãéèëêíìïîóòöôõúùüûñç';
    const target = 'aaaaaeeeeiiiiooooouuuunc';
    var text = input.toLowerCase();
    for (var i = 0; i < source.length; i++) {
      text = text.replaceAll(source[i], target[i]);
    }
    return text
        .replaceAll(RegExp(r'[^a-z0-9]+'), '-')
        .replaceAll(RegExp(r'^-+|-+$'), '');
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final app = context.read<AppState>();
    final trialText = _trialDays.text.trim();
    final result = await app.createCompany(
      companyName: _name.text.trim(),
      slug: _slug.text.trim().toLowerCase(),
      email: _email.text.trim(),
      firstName: _firstName.text.trim(),
      planCode: _planCode,
      trialDays: trialText.isEmpty ? null : int.tryParse(trialText),
    );
    if (!mounted) return;
    if (result == null) {
      _notify(app.errorMessage ?? 'No se pudo crear la empresa.', error: true);
      return;
    }
    setState(() => _result = result);
  }

  void _createAnother() {
    setState(() {
      _result = null;
      _slugEdited = false;
      _trialEdited = false;
      _planCode = null;
      _name.clear();
      _slug.clear();
      _email.clear();
      _firstName.clear();
      _trialDays.clear();
    });
    final plans = context.read<AppState>().plans;
    if (plans.isNotEmpty) {
      _selectPlan(
        plans.firstWhere((plan) => plan.isDefault, orElse: () => plans.first),
      );
    }
  }

  Future<void> _copyAll() async {
    final result = _result;
    if (result == null) return;
    final text = [
      result.credentials,
      if (result.bookingUrl.isNotEmpty) 'Reservas: ${result.bookingUrl}',
    ].join('\n');
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) _notify('Credenciales copiadas.');
  }

  String _formatDate(DateTime date) {
    final day = date.day.toString().padLeft(2, '0');
    final month = date.month.toString().padLeft(2, '0');
    return '$day/$month/${date.year}';
  }

  void _notify(String message, {bool error = false}) {    final theme = Theme.of(context);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: error
            ? theme.colorScheme.error
            : theme.brightness == Brightness.dark
            ? context.palette.surfaceAlt
            : context.palette.onSurface,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_result == null ? 'Crear empresa' : 'Empresa creada'),
      ),
      body: _result == null ? _form(context) : _success(context, _result!),
    );
  }

  Widget _form(BuildContext context) {
    final app = context.watch<AppState>();
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 40),
        children: [
          const Text(
            'NUEVA EMPRESA',
            style: TextStyle(
              fontSize: 30,
              fontWeight: FontWeight.w900,
              letterSpacing: -0.8,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Crea la cuenta mientras hablas con el cliente y entrégale las '
            'credenciales al finalizar.',
            style: TextStyle(color: context.palette.muted, height: 1.4),
          ),
          if (app.errorMessage != null) ...[
            const SizedBox(height: 16),
            ErrorNote(app.errorMessage!),
          ],
          const SectionLabel('Empresa'),
          SurfaceCard(
            child: Column(
              children: [
                TextFormField(
                  key: const Key('create-company-name'),
                  controller: _name,
                  textCapitalization: TextCapitalization.words,
                  maxLength: 180,
                  decoration: const InputDecoration(
                    labelText: 'Nombre comercial',
                    helperText: 'Tal como lo verá el cliente.',
                  ),
                  validator: _validateName,
                ),
                const SizedBox(height: 8),
                TextFormField(
                  key: const Key('create-company-slug'),
                  controller: _slug,
                  maxLength: 100,
                  autocorrect: false,
                  enableSuggestions: false,
                  onChanged: (_) => _slugEdited = true,
                  decoration: const InputDecoration(
                    labelText: 'Identificador público',
                    helperText: 'Se usa en el enlace de reservas.',
                  ),
                  validator: _validateSlug,
                ),
              ],
            ),
          ),
          const SectionLabel('Cuenta del cliente'),
          SurfaceCard(
            child: Column(
              children: [
                TextFormField(
                  key: const Key('create-company-email'),
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                  decoration: const InputDecoration(
                    labelText: 'Correo del dueño',
                    helperText: 'Con este correo iniciará sesión.',
                  ),
                  validator: _validateEmail,
                ),
                const SizedBox(height: 8),
                TextFormField(
                  key: const Key('create-company-first-name'),
                  controller: _firstName,
                  textCapitalization: TextCapitalization.words,
                  maxLength: 150,
                  decoration: const InputDecoration(
                    labelText: 'Nombre del dueño (opcional)',
                  ),
                ),
              ],
            ),
          ),
          const SectionLabel('Plan'),
          SurfaceCard(
            child: Column(
              children: [
                if (app.plans.isEmpty)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'Se usará el plan predeterminado de la plataforma.',
                      style: TextStyle(
                        color: context.palette.muted,
                        fontSize: 12.5,
                      ),
                    ),
                  )
                else ...[
                  InputDecorator(
                    decoration: const InputDecoration(labelText: 'Plan'),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        key: const Key('create-company-plan'),
                        isExpanded: true,
                        value: _planCode,
                        items: [
                          for (final plan in app.plans)
                            DropdownMenuItem(
                              value: plan.code,
                              child: Text(plan.name),
                            ),
                        ],
                        onChanged: (code) {
                          if (code == null) return;
                          _selectPlan(
                            app.plans.firstWhere((plan) => plan.code == code),
                          );
                        },
                      ),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      _selectedPlan(app.plans) == null
                          ? 'Elige el plan del cliente.'
                          : '${_selectedPlan(app.plans)!.priceLabel} · '
                                '${_selectedPlan(app.plans)!.trialDays} días de prueba',
                      style: TextStyle(
                        color: context.palette.muted,
                        fontSize: 11.5,
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 8),
                TextFormField(
                  key: const Key('create-company-trial-days'),
                  controller: _trialDays,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  onChanged: (_) => _trialEdited = true,
                  decoration: const InputDecoration(
                    labelText: 'Días de prueba',
                    helperText: '0 = activa de inmediato.',
                  ),
                  validator: _validateTrialDays,
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'La contraseña se genera automáticamente. Se mostrará una sola vez '
            'para que la compartas con el cliente.',
            style: TextStyle(
              color: context.palette.muted,
              fontSize: 12,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 22),
          FilledButton.icon(
            key: const Key('create-company-submit'),
            onPressed: app.busy ? null : _submit,
            icon: const Icon(Icons.add_business_rounded, size: 18),
            label: Text(app.busy ? 'Creando…' : 'Crear empresa'),
          ),
        ],
      ),
    );
  }

  Widget _success(BuildContext context, CompanyCreationResult result) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 40),
      children: [
        const SizedBox(height: 8),
        Icon(
          Icons.check_circle_rounded,
          size: 46,
          color: Theme.of(context).colorScheme.primary,
        ),
        const SizedBox(height: 14),
        const Text(
          'Empresa creada',
          style: TextStyle(
            fontSize: 30,
            fontWeight: FontWeight.w900,
            letterSpacing: -0.8,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Comparte estas credenciales con el cliente. La contraseña no se '
          'volverá a mostrar.',
          style: TextStyle(color: context.palette.muted, height: 1.4),
        ),
        const SectionLabel('Credenciales'),
        SurfaceCard(
          key: const Key('create-company-success'),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _CredentialRow(label: 'Empresa', value: result.companyName),
              _CredentialRow(label: 'Usuario', value: result.ownerEmail),
              _CredentialRow(
                label: 'Contraseña temporal',
                value: result.temporaryPassword,
              ),
              _CredentialRow(label: 'Identificador', value: result.slug),
              if (result.planName.isNotEmpty)
                _CredentialRow(label: 'Plan', value: result.planName),
              if (result.trialEndsAt != null)
                _CredentialRow(
                  label: 'Prueba',
                  value: 'Hasta ${_formatDate(result.trialEndsAt!.toLocal())}',
                ),
            ],
          ),
        ),
        if (result.bookingUrl.isNotEmpty) ...[
          const SizedBox(height: 12),
          SurfaceCard(
            child: Row(
              children: [
                Icon(
                  Icons.link_rounded,
                  size: 16,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    result.bookingUrl,
                    style: const TextStyle(fontSize: 11.5),
                  ),
                ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 22),
        FilledButton.icon(
          key: const Key('create-company-copy-all'),
          onPressed: _copyAll,
          icon: const Icon(Icons.copy_rounded, size: 18),
          label: const Text('Copiar credenciales'),
        ),
        const SizedBox(height: 10),
        OutlinedButton.icon(
          key: const Key('create-company-again'),
          onPressed: _createAnother,
          icon: const Icon(Icons.add_rounded, size: 18),
          label: const Text('Crear otra empresa'),
        ),
        const SizedBox(height: 4),
        TextButton(
          key: const Key('create-company-done'),
          onPressed: () => Navigator.of(context).maybePop(),
          child: const Text('Volver'),
        ),
      ],
    );
  }

  String? _validateName(String? value) {
    final name = (value ?? '').trim();
    if (name.isEmpty) return 'Escribe el nombre comercial.';
    if (name.length > 180) return 'Máximo 180 caracteres.';
    return null;
  }

  String? _validateSlug(String? value) {
    final slug = (value ?? '').trim();
    if (slug.isEmpty) return 'Escribe el identificador público.';
    if (!RegExp(_slugPattern).hasMatch(slug)) {
      return 'Usa letras, números, guiones o guiones bajos (máximo 100).';
    }
    if (_reservedSlugs.contains(slug.toLowerCase())) {
      return 'Este identificador está reservado por la plataforma.';
    }
    return null;
  }

  String? _validateEmail(String? value) {
    final email = (value ?? '').trim();
    if (email.isEmpty || !RegExp(_emailPattern).hasMatch(email)) {
      return 'Escribe un correo válido.';
    }
    return null;
  }

  String? _validateTrialDays(String? value) {
    final text = (value ?? '').trim();
    if (text.isEmpty) return null;
    final days = int.tryParse(text);
    if (days == null || days < 0 || days > 365) {
      return 'Ingresa entre 0 y 365 días.';
    }
    return null;
  }
}

class _CredentialRow extends StatelessWidget {
  const _CredentialRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label.toUpperCase(),
            style: TextStyle(
              color: context.palette.muted,
              fontSize: 10.5,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.2,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}
