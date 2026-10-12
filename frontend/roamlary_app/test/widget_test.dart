import 'package:flutter_test/flutter_test.dart';

import 'package:roamlary_app/core/app_theme.dart';
import 'package:roamlary_app/data/companion_service.dart';
import 'package:roamlary_app/data/mock_repository.dart';
import 'package:roamlary_app/main.dart';
import 'package:roamlary_app/screens/login_screen.dart';
import 'package:roamlary_app/state/app_state.dart';

void main() {
  testWidgets('App builds and shows the login screen', (tester) async {
    await tester.pumpWidget(RoamlaryApp(repo: MockRepository()));
    await tester.pump();

    expect(find.text('Roamlary'), findsOneWidget);
    expect(find.byType(LoginScreen), findsOneWidget);
  });

  testWidgets('Guest / demo path reaches the home shell', (tester) async {
    await tester.pumpWidget(RoamlaryApp(repo: MockRepository()));
    await tester.pump();

    await tester.tap(find.text('Explore demo'));
    // allow the guest sign-in + navigation to settle
    await tester.pump(const Duration(milliseconds: 600));
    await tester.pumpAndSettle();

    expect(find.text('Home'), findsOneWidget);
  });

  testWidgets('Theme constructs without error', (tester) async {
    final light = AppTheme.light();
    final dark = AppTheme.dark();
    expect(light.useMaterial3, isTrue);
    expect(dark.useMaterial3, isTrue);
  });

  testWidgets('AppState exposes the repository and starts signed out',
      (tester) async {
    final state = AppState(MockRepository());
    expect(state.isSignedIn, isFalse);
    expect(state.repo, isA<MockRepository>());
    expect(const CompanionService(), isA<CompanionService>());
  });
}
