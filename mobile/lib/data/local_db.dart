import 'package:sembast/sembast.dart';

export 'package:sembast/sembast.dart' show Database;

import 'local_db_io.dart'
    if (dart.library.js_interop) 'local_db_web.dart' as platform;

Future<Database> openAppDatabase() => platform.openAppDatabase();
