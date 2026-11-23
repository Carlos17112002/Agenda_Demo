import 'package:path_provider/path_provider.dart';
import 'package:sembast/sembast_io.dart';

Future<Database> openAppDatabase() async {
  final directory = await getApplicationSupportDirectory();
  final path = '${directory.path}/agenda_mobile.db';
  return databaseFactoryIo.openDatabase(path);
}
