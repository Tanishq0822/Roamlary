import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/app_theme.dart';
import 'core/config.dart';
import 'data/api_repository.dart';
import 'data/app_repository.dart';
import 'data/companion_service.dart';
import 'data/mock_repository.dart';
import 'screens/login_screen.dart';
import 'state/app_state.dart';

void main() {
  // Composition root: pick the data source from a single switch. Default is the
  // mock repo so the demo runs with no backend. Flip AppConfig.useMocks to use
  // the real FastAPI contract instead.
  final AppRepository repo =
      AppConfig.useMocks ? MockRepository() : ApiRepository();

  runApp(RoamlaryApp(repo: repo));
}

class RoamlaryApp extends StatelessWidget {
  const RoamlaryApp({super.key, required this.repo});

  final AppRepository repo;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AppState>(
          create: (_) => AppState(repo),
        ),
        Provider<CompanionService>(create: (_) => const CompanionService()),
      ],
      child: MaterialApp(
        title: AppConfig.appName,
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light(),
        darkTheme: AppTheme.dark(),
        // Owner-directed palette (white + light green + light purple) is the
        // light theme - force it so the requested look always shows.
        themeMode: ThemeMode.light,
        home: const LoginScreen(),
      ),
    );
  }
}
