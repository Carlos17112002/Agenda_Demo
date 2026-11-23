import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../core/branding.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

const _maxLogoBytes = 2 * 1024 * 1024;
const _logoExtensions = ['.png', '.jpg', '.jpeg', '.webp'];
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
const _presets = [
  ('Carmesí', '#E50914', '#8B0000'),
  ('Océano', '#1E6FFF', '#0B3D91'),
  ('Bosque', '#2E7D32', '#1B5E20'),
  ('Violeta', '#7C4DFF', '#4527A0'),
  ('Grafito', '#BDBDBD', '#424242'),
];

class PickedLogo {
  const PickedLogo({required this.bytes, required this.filename});

  final List<int> bytes;
  final String filename;
}

typedef LogoPicker = Future<PickedLogo?> Function();

class BrandingScreen extends StatefulWidget {
  const BrandingScreen({super.key, this.pickLogo});

  final LogoPicker? pickLogo;

  @override
  State<BrandingScreen> createState() => _BrandingScreenState();
}

class _BrandingScreenState extends State<BrandingScreen> {
  final _formKey = GlobalKey<FormState>();
  TextEditingController? _name;
  TextEditingController? _slug;
  TextEditingController? _primary;
  TextEditingController? _secondary;
  bool _dark = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_name != null) return;
    final company = context.read<AppState>().bootstrap?.company ?? const {};
    _name = _controller(
      (company['display_name'] ?? company['name'] ?? '').toString(),
    );
    _slug = _controller((company['slug'] ?? '').toString());
    _primary = _controller((company['primary_color'] ?? '#E50914').toString());
    _secondary = _controller(
      (company['secondary_color'] ?? '#8B0000').toString(),
    );
    _dark = company['theme_mode'] == 'dark';
  }

  TextEditingController _controller(String value) {
    final controller = TextEditingController(text: value);
    controller.addListener(_refresh);
    return controller;
  }

  void _refresh() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _name?.dispose();
    _slug?.dispose();
    _primary?.dispose();
    _secondary?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final bootstrap = app.bootstrap;
    return Scaffold(
      appBar: AppBar(title: const Text('Marca de empresa')),
      body: bootstrap == null
          ? const Center(child: CircularProgressIndicator())
          : !app.can('company.manage')
          ? const EmptyState(
              icon: Icons.lock_outline_rounded,
              title: 'Marca de empresa',
              message: 'No tienes permiso para editar la marca.',
            )
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 4, 20, 40),
                children: [
                  Text(
                    'Así verán tus clientes la empresa en la app y en la página pública de reservas.',
                    style: TextStyle(
                      color: context.palette.muted,
                      height: 1.4,
                    ),
                  ),
                  const SectionLabel('Vista previa'),
                  _Preview(
                    name: _name!.text,
                    primary: _primary!.text,
                    secondary: _secondary!.text,
                    company: bootstrap.company,
                    dark: _dark,
                  ),
                  const SectionLabel('Identidad'),
                  SurfaceCard(
                    child: Column(
                      children: [
                        TextFormField(
                          key: const Key('branding-name'),
                          controller: _name,
                          textCapitalization: TextCapitalization.words,
                          maxLength: 180,
                          decoration: const InputDecoration(
                            labelText: 'Nombre visible',
                            helperText: 'Se muestra en la app y en la página de reservas.',
                          ),
                          validator: _validateName,
                        ),
                        const SizedBox(height: 8),
                        TextFormField(
                          key: const Key('branding-slug'),
                          controller: _slug,
                          maxLength: 100,
                          autocorrect: false,
                          enableSuggestions: false,
                          decoration: const InputDecoration(
                            labelText: 'Identificador público',
                            helperText: 'Aparece en el enlace de reservas de la empresa.',
                          ),
                          validator: _validateSlug,
                        ),
                      ],
                    ),
                  ),
                  _SlugNote(
                    current: (bootstrap.company['slug'] ?? '').toString(),
                    slug: _slug!.text.trim().toLowerCase(),
                    bookingUrl: _bookingUrl(
                      bootstrap.company['booking_url']?.toString() ?? '',
                      _slug!.text.trim().toLowerCase(),
                    ),
                  ),
                  const SectionLabel('Colores'),
                  SurfaceCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: TextFormField(
                                key: const Key('branding-primary'),
                                controller: _primary,
                                autocorrect: false,
                                textCapitalization:
                                    TextCapitalization.characters,
                                decoration: const InputDecoration(
                                  labelText: 'Color principal',
                                ),
                                validator: _validateColor,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: TextFormField(
                                key: const Key('branding-secondary'),
                                controller: _secondary,
                                autocorrect: false,
                                textCapitalization:
                                    TextCapitalization.characters,
                                decoration: const InputDecoration(
                                  labelText: 'Color secundario',
                                ),
                                validator: _validateColor,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 14),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            for (final preset in _presets)
                              _PresetChip(
                                label: preset.$1,
                                primary: preset.$2,
                                secondary: preset.$3,
                                onTap: () => _applyPreset(preset.$2, preset.$3),
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SectionLabel('Fondo'),
                  SurfaceCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Elige el fondo de la app y de la página pública de reservas.',
                          style: TextStyle(
                            color: context.palette.muted,
                            fontSize: 12.5,
                            height: 1.35,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: _ThemeOption(
                                key: const Key('branding-theme-light'),
                                label: 'Claro',
                                icon: Icons.light_mode_rounded,
                                selected: !_dark,
                                onTap: () => setState(() => _dark = false),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: _ThemeOption(
                                key: const Key('branding-theme-dark'),
                                label: 'Oscuro',
                                icon: Icons.dark_mode_rounded,
                                selected: _dark,
                                onTap: () => setState(() => _dark = true),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SectionLabel('Logo'),
                  SurfaceCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            CompanyLogo(
                              company: _previewCompany(bootstrap.company),
                              size: 64,
                            ),
                            const SizedBox(width: 14),
                            Expanded(
                              child: Text(
                                bootstrap.branding.hasLogo
                                    ? 'Logo actual de la empresa.'
                                    : 'Aún no hay logo: se muestra la inicial.',
                                style: TextStyle(
                                  color: context.palette.muted,
                                  fontSize: 12.5,
                                  height: 1.35,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 14),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                key: const Key('branding-upload'),
                                onPressed: app.busy ? null : _uploadLogo,
                                icon: const Icon(
                                  Icons.upload_rounded,
                                  size: 18,
                                ),
                                label: Text(
                                  bootstrap.branding.hasLogo
                                      ? 'Cambiar logo'
                                      : 'Subir logo',
                                ),
                              ),
                            ),
                            if (bootstrap.branding.hasLogo) ...[
                              const SizedBox(width: 10),
                              IconButton(
                                key: const Key('branding-remove-logo'),
                                tooltip: 'Quitar logo',
                                onPressed: app.busy ? null : _removeLogo,
                                color: Theme.of(context).colorScheme.error,
                                icon: const Icon(Icons.delete_outline_rounded),
                              ),
                            ],
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'PNG, JPEG o WebP · máximo 2 MB.',
                          style: TextStyle(
                            color: context.palette.muted,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 22),
                  FilledButton.icon(
                    key: const Key('branding-save'),
                    onPressed: app.busy ? null : _save,
                    icon: const Icon(Icons.save_rounded, size: 18),
                    label: Text(app.busy ? 'Guardando…' : 'Guardar cambios'),
                  ),
                ],
              ),
            ),
    );
  }

  Map<String, dynamic> _previewCompany(Map<String, dynamic> company) => {
    ...company,
    'display_name': _name!.text,
    'primary_color': _primary!.text,
    'secondary_color': _secondary!.text,
    'theme_mode': _dark ? 'dark' : 'light',
  };

  void _applyPreset(String primary, String secondary) {
    _primary!.text = primary;
    _secondary!.text = secondary;
  }

  String? _validateName(String? value) {
    final name = (value ?? '').trim();
    if (name.isEmpty) return 'Escribe el nombre visible de la empresa.';
    if (name.length > 180) return 'Máximo 180 caracteres.';
    return null;
  }

  String? _validateSlug(String? value) {
    final slug = (value ?? '').trim();
    if (slug.isEmpty) return 'Escribe el identificador público.';
    if (!RegExp(r'^[-a-zA-Z0-9_]{1,100}$').hasMatch(slug)) {
      return 'Usa letras, números, guiones o guiones bajos (máximo 100).';
    }
    if (_reservedSlugs.contains(slug.toLowerCase())) {
      return 'Este identificador está reservado por la plataforma.';
    }
    return null;
  }

  String? _validateColor(String? value) {
    final color = (value ?? '').trim();
    if (!RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(color)) {
      return 'Usa un color hexadecimal con formato #RRGGBB.';
    }
    return null;
  }

  static String _bookingUrl(String current, String slug) {
    final base = current.contains('/b/')
        ? current.substring(0, current.indexOf('/b/'))
        : current;
    if (base.isEmpty) return '';
    return '$base/b/$slug/';
  }

  Future<void> _save() async {
    FocusScope.of(context).unfocus();
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final app = context.read<AppState>();
    final saved = await app.updateBranding(
      displayName: _name!.text.trim(),
      slug: _slug!.text.trim().toLowerCase(),
      primaryColor: _primary!.text.trim(),
      secondaryColor: _secondary!.text.trim(),
      darkMode: _dark,
    );
    if (!mounted) return;
    _notify(
      saved ? 'Marca actualizada.' : app.errorMessage ?? 'No se pudo guardar.',
      error: !saved,
    );
  }

  Future<void> _uploadLogo() async {
    final picker = widget.pickLogo ?? _pickFromGallery;
    PickedLogo? picked;
    try {
      picked = await picker();
    } catch (_) {
      if (mounted) _notify('No se pudo abrir la galería.', error: true);
      return;
    }
    if (picked == null || !mounted) return;
    if (picked.bytes.length > _maxLogoBytes) {
      _notify('El logo no puede superar 2 MB.', error: true);
      return;
    }
    final name = picked.filename.toLowerCase();
    if (!_logoExtensions.any(name.endsWith)) {
      _notify('Sube un logo PNG, JPEG o WebP.', error: true);
      return;
    }
    final app = context.read<AppState>();
    final saved = await app.uploadLogo(
      bytes: picked.bytes,
      filename: picked.filename,
    );
    if (!mounted) return;
    _notify(
      saved ? 'Logo actualizado.' : app.errorMessage ?? 'No se pudo subir.',
      error: !saved,
    );
  }

  Future<void> _removeLogo() async {
    final app = context.read<AppState>();
    final removed = await app.removeLogo();
    if (!mounted) return;
    _notify(
      removed ? 'Logo eliminado.' : app.errorMessage ?? 'No se pudo quitar.',
      error: !removed,
    );
  }

  void _notify(String message, {bool error = false}) {
    final theme = Theme.of(context);
    final palette = context.palette;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: error
            ? theme.colorScheme.error
            : theme.brightness == Brightness.dark
            ? palette.surfaceAlt
            : palette.onSurface,
      ),
    );
  }
}

Future<PickedLogo?> _pickFromGallery() async {
  final file = await ImagePicker().pickImage(
    source: ImageSource.gallery,
    maxWidth: 2000,
    maxHeight: 2000,
  );
  if (file == null) return null;
  return PickedLogo(bytes: await file.readAsBytes(), filename: file.name);
}

class _Preview extends StatelessWidget {
  const _Preview({
    required this.name,
    required this.primary,
    required this.secondary,
    required this.company,
    required this.dark,
  });

  final String name;
  final String primary;
  final String secondary;
  final Map<String, dynamic> company;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final branding = Branding(
      displayName: name,
      primary: Branding.parseHex(primary, const Color(0xFFE50914)),
      secondary: Branding.parseHex(secondary, const Color(0xFF8B0000)),
      brightness: dark ? Brightness.dark : Brightness.light,
    );
    final background = dark ? const Color(0xFF0E0E10) : const Color(0xFFFFFFFF);
    final foreground = dark ? Colors.white : const Color(0xFF121317);
    final border = dark ? const Color(0xFF252525) : const Color(0xFFE4E4E9);
    return Container(
      key: const Key('branding-preview'),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CompanyLogo(
                company: {
                  ...company,
                  'display_name': name,
                  'primary_color': primary,
                  'secondary_color': secondary,
                },
                size: 52,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name.trim().isEmpty ? 'Tu empresa' : name.trim(),
                      style: TextStyle(
                        color: foreground,
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Reserva tu hora en línea',
                      style: TextStyle(
                        color: branding.primary,
                        fontSize: 11.5,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: Row(
              children: [
                Expanded(
                  child: Container(
                    height: 34,
                    color: branding.primary,
                    alignment: Alignment.center,
                    child: Text(
                      'Reservar',
                      style: TextStyle(
                        color: branding.onPrimary,
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
                Expanded(
                  child: Container(
                    height: 34,
                    color: branding.secondary,
                    alignment: Alignment.center,
                    child: Text(
                      'Mi cuenta',
                      style: TextStyle(
                        color: branding.onSecondary,
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SlugNote extends StatelessWidget {
  const _SlugNote({
    required this.current,
    required this.slug,
    required this.bookingUrl,
  });

  final String current;
  final String slug;
  final String bookingUrl;

  @override
  Widget build(BuildContext context) {
    final changed = slug.isNotEmpty && slug != current;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: changed
              ? Theme.of(context).colorScheme.error.withValues(alpha: 0.12)
              : context.palette.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: changed
                ? Theme.of(context).colorScheme.error
                : context.palette.border,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.link_rounded,
                  size: 16,
                  color: changed
                      ? Theme.of(context).colorScheme.error
                      : Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    bookingUrl,
                    style: const TextStyle(fontSize: 11.5),
                  ),
                ),
              ],
            ),
            if (changed) ...[
              const SizedBox(height: 6),
              Text(
                'El enlace público cambiará. '
                'Los enlaces anteriores dejarán de funcionar.',
                style: const TextStyle(fontSize: 11.5, height: 1.35),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _PresetChip extends StatelessWidget {
  const _PresetChip({
    required this.label,
    required this.primary,
    required this.secondary,
    required this.onTap,
  });

  final String label;
  final String primary;
  final String secondary;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: Container(
        padding: const EdgeInsets.fromLTRB(8, 5, 12, 5),
        decoration: BoxDecoration(
          color: context.palette.surfaceAlt,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: context.palette.border),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _dot(primary, 10),
            const SizedBox(width: 3),
            _dot(secondary, 10),
            const SizedBox(width: 7),
            Text(label, style: const TextStyle(fontSize: 11.5)),
          ],
        ),
      ),
    );
  }

  Widget _dot(String color, double size) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(
      color: Branding.parseHex(color, AgendaColors.muted),
      shape: BoxShape.circle,
    ),
  );
}

class _ThemeOption extends StatelessWidget {
  const _ThemeOption({
    super.key,
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final palette = context.palette;
    final accent = Theme.of(context).colorScheme.primary;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        decoration: BoxDecoration(
          color: selected
              ? accent.withValues(alpha: 0.12)
              : palette.surfaceAlt,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: selected ? accent : palette.border,
            width: selected ? 1.4 : 1,
          ),
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 18,
              color: selected ? accent : palette.muted,
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                fontSize: 13,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
