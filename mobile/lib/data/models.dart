import '../core/branding.dart';

class Bootstrap {
  Bootstrap({
    required this.user,
    required this.company,
    required this.membership,
    required this.permissions,
    required this.features,
    required this.modules,
    required this.billingState,
    required this.subscription,
    required this.branches,
    required this.syncResources,
    required this.serverTime,
    this.companies = const [],
    this.worker,
  });

  final Map<String, dynamic> user;
  final Map<String, dynamic> company;
  final Map<String, dynamic> membership;
  final List<String> permissions;
  final Map<String, dynamic> features;
  final Map<String, dynamic> modules;
  final String billingState;
  final Map<String, dynamic>? subscription;
  final List<Map<String, dynamic>> branches;
  final List<String> syncResources;
  final String serverTime;
  final List<Map<String, dynamic>> companies;
  final Map<String, dynamic>? worker;

  String? get workerId => worker?['id']?.toString();
  String? get workerName => worker?['name']?.toString();

  String get userName {
    final first = (user['first_name'] ?? '').toString().trim();
    final last = (user['last_name'] ?? '').toString().trim();
    final full = '$first $last'.trim();
    return full.isEmpty ? (user['email'] ?? 'Usuario').toString() : full;
  }

  Branding get branding => Branding.fromCompany(company);
  String get companyName => branding.displayName;
  String get companyBookingUrl => (company['booking_url'] ?? '').toString();
  String get role =>
      (membership['role_display'] ?? membership['role'] ?? '').toString();
  bool get hasSubscription => subscription != null;
  bool get isSaasAdmin => user['is_saas_admin'] == true;
  bool get mustChangePassword => user['must_change_password'] == true;
  Map<String, dynamic>? get defaultBranch =>
      membership['default_branch'] is Map
          ? _map(membership['default_branch'])
          : null;
  String? get defaultBranchId => defaultBranch?['id']?.toString();
  bool moduleEnabled(String module) => modules[module] == true;

  factory Bootstrap.fromJson(Map<String, dynamic> json) {
    return Bootstrap(
      user: _map(json['user']),
      company: _map(json['company']),
      membership: _map(json['membership']),
      permissions: _list(json['permissions']).map((e) => e.toString()).toList(),
      features: _map(json['features']),
      modules: _map(json['modules']),
      billingState: (json['billing_state'] ?? 'inactive').toString(),
      subscription: json['subscription'] is Map
          ? _map(json['subscription'])
          : null,
      branches: _list(json['branches']).map(_map).toList(),
      syncResources: _list(json['sync_resources'])
          .map((e) => e.toString())
          .toList(),
      serverTime: (json['server_time'] ?? '').toString(),
      companies: _list(json['companies']).map(_map).toList(),
      worker: json['worker'] is Map ? _map(json['worker']) : null,
    );
  }

  Map<String, dynamic> toJson() => {
    'user': user,
    'company': company,
    'membership': membership,
    'permissions': permissions,
    'features': features,
    'modules': modules,
    'billing_state': billingState,
    'subscription': subscription,
    'branches': branches,
    'sync_resources': syncResources,
    'server_time': serverTime,
    'companies': companies,
    'worker': worker,
  };
}

class BookingRecord {
  BookingRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get serviceName => (raw['service_name'] ?? 'Servicio').toString();
  String get workerName => (raw['worker_name'] ?? '').toString();
  String get customerName => (raw['customer_name'] ?? '').toString();
  String get status => (raw['status'] ?? 'scheduled').toString();
  String get statusDisplay => (raw['status_display'] ?? status).toString();
  String get publicCode => (raw['public_code'] ?? '').toString();
  DateTime? get startAt =>
      DateTime.tryParse((raw['start_at'] ?? '').toString());
  DateTime? get endAt => DateTime.tryParse((raw['end_at'] ?? '').toString());
  bool get isActive => status == 'scheduled' || status == 'confirmed';
}

class ProductRecord {
  ProductRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get sku => (raw['sku'] ?? '').toString();
  String get name => (raw['name'] ?? 'Producto').toString();
  String get price => (raw['price'] ?? '0').toString();
  bool get active => raw['active'] != false;
  double get reorderPoint => double.tryParse('${raw['reorder_point']}') ?? 0;
}

class WarehouseRecord {
  WarehouseRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get name => (raw['name'] ?? 'Bodega').toString();
  bool get active => raw['active'] != false;
}

class ServiceRecord {
  ServiceRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get name => (raw['name'] ?? 'Servicio').toString();
  bool get active => raw['active'] != false;
}

class WorkerRecord {
  WorkerRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get name {
    final first = (raw['first_name'] ?? '').toString();
    final last = (raw['last_name'] ?? '').toString();
    return '$first $last'.trim().isEmpty
        ? 'Profesional'
        : '$first $last'.trim();
  }

  bool get active => raw['active'] != false;
}

class CustomerRecord {
  CustomerRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get name {
    final first = (raw['first_name'] ?? '').toString();
    final last = (raw['last_name'] ?? '').toString();
    return '$first $last'.trim().isEmpty ? 'Cliente' : '$first $last'.trim();
  }

  bool get active => raw['active'] != false;
}

class StockRow {
  StockRow(this.raw, this.product);

  final Map<String, dynamic> raw;
  final ProductRecord? product;

  String get warehouseName => (raw['warehouse_name'] ?? '').toString();
  double get quantity => double.tryParse('${raw['quantity']}') ?? 0;
  double get averageCost => double.tryParse('${raw['average_cost']}') ?? 0;
  bool get lowStock {
    final point = product?.reorderPoint ?? 0;
    return point > 0 && quantity <= point;
  }
}

class NotificationRecord {
  NotificationRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get title => (raw['title'] ?? '').toString();
  String get body => (raw['body'] ?? '').toString();
  String get kind => (raw['kind'] ?? 'system').toString();
  bool get unread => raw['read_at'] == null;
  DateTime? get createdAt =>
      DateTime.tryParse((raw['created_at'] ?? '').toString());
}

class OutboxItem {
  OutboxItem({
    required this.clientId,
    required this.type,
    required this.payload,
    required this.createdAt,
    this.status = 'pending',
    this.error,
    this.companyId,
  });

  final String clientId;
  final String type;
  final Map<String, dynamic> payload;
  final String createdAt;
  String status;
  String? error;
  final String? companyId;

  bool get pending => status == 'pending';

  Map<String, dynamic> toJson() => {
    'client_id': clientId,
    'type': type,
    'payload': payload,
    'created_at': createdAt,
    'status': status,
    'error': error,
    'company_id': companyId,
  };

  factory OutboxItem.fromJson(Map<String, dynamic> json) => OutboxItem(
    clientId: (json['client_id'] ?? '').toString(),
    type: (json['type'] ?? '').toString(),
    payload: _map(json['payload']),
    createdAt: (json['created_at'] ?? '').toString(),
    status: (json['status'] ?? 'pending').toString(),
    error: json['error']?.toString(),
    companyId: json['company_id']?.toString(),
  );
}

class PlanOption {
  PlanOption({
    required this.code,
    required this.name,
    required this.price,
    required this.currency,
    required this.billingPeriod,
    required this.trialDays,
    this.isDefault = false,
  });

  final String code;
  final String name;
  final double price;
  final String currency;
  final String billingPeriod;
  final int trialDays;
  final bool isDefault;

  String get priceLabel {
    if (price <= 0) return 'Gratis';
    final amount = price == price.roundToDouble()
        ? price.toStringAsFixed(0)
        : price.toStringAsFixed(2);
    final period = billingPeriod == 'yearly' ? '/año' : '/mes';
    return '$currency $amount$period';
  }

  factory PlanOption.fromJson(Map<String, dynamic> json) {
    return PlanOption(
      code: (json['code'] ?? '').toString(),
      name: (json['name'] ?? '').toString(),
      price: double.tryParse('${json['price'] ?? ''}') ?? 0,
      currency: (json['currency'] ?? '').toString(),
      billingPeriod: (json['billing_period'] ?? '').toString(),
      trialDays: (json['trial_days'] as num?)?.toInt() ?? 0,
      isDefault: json['is_default'] == true,
    );
  }
}

class CompanyCreationResult {
  CompanyCreationResult({
    required this.companyId,
    required this.companyName,
    required this.slug,
    required this.ownerEmail,
    required this.temporaryPassword,
    required this.bookingUrl,
    this.planName = '',
    this.planCode = '',
    this.trialEndsAt,
  });

  final String companyId;
  final String companyName;
  final String slug;
  final String ownerEmail;
  final String temporaryPassword;
  final String bookingUrl;
  final String planName;
  final String planCode;
  final DateTime? trialEndsAt;

  String get credentials =>
      'Empresa: $companyName\n'
      'Usuario: $ownerEmail\n'
      'Contraseña temporal: $temporaryPassword';

  factory CompanyCreationResult.fromJson(Map<String, dynamic> json) {
    final subscription = _map(json['subscription']);
    final plan = _map(subscription['plan']);
    final trialEndsAt = DateTime.tryParse(
      (subscription['trial_ends_at'] ?? '').toString(),
    );
    return CompanyCreationResult(
      companyId: (json['company_id'] ?? '').toString(),
      companyName: (json['company_name'] ?? '').toString(),
      slug: (json['slug'] ?? '').toString(),
      ownerEmail: (json['owner_email'] ?? '').toString(),
      temporaryPassword: (json['temporary_password'] ?? '').toString(),
      bookingUrl: (json['booking_url'] ?? '').toString(),
      planName: (plan['name'] ?? '').toString(),
      planCode: (plan['code'] ?? '').toString(),
      trialEndsAt: trialEndsAt,
    );
  }
}

Map<String, dynamic> _map(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return value.map((k, v) => MapEntry(k.toString(), v));
  return <String, dynamic>{};
}

List<dynamic> _list(dynamic value) => value is List ? value : const [];
