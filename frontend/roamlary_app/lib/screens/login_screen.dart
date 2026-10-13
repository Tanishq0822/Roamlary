import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/config.dart';
import '../state/app_state.dart';
import 'home_shell.dart';

/// Email + password entry point with proper client-side validation.
///
/// The backend enforces `extra="forbid"`, EmailStr and password length
/// 8-128; this screen mirrors those rules (plus a strength meter and a
/// confirm-password step) so bad input never costs a round-trip.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();
  bool _registerMode = false;
  bool _obscure = true;
  bool _obscureConfirm = true;

  // Mirrors backend EmailStr (pragmatic RFC 5322 subset).
  static final _emailRe = RegExp(
      r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$");

  @override
  void dispose() {
    _nameCtrl.dispose();
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  /// 0..4 — length, lowercase, uppercase, digit, symbol (min length 8 first).
  int get _strength {
    final p = _passwordCtrl.text;
    if (p.isEmpty) return 0;
    var s = 0;
    if (p.length >= 8) s++;
    if (p.length >= 12) s++;
    if (p.contains(RegExp(r'[a-z]')) && p.contains(RegExp(r'[A-Z]'))) s++;
    if (p.contains(RegExp(r'\d'))) s++;
    if (p.contains(RegExp(r'[^\w\s]'))) s++;
    return s > 4 ? 4 : s;
  }

  String? _validateEmail(String? v) {
    final value = v?.trim() ?? '';
    if (value.isEmpty) return 'Enter your email';
    if (!_emailRe.hasMatch(value)) return 'Enter a valid email address';
    return null;
  }

  String? _validatePassword(String? v) {
    final value = v ?? '';
    if (value.isEmpty) return 'Enter your password';
    if (!_registerMode) return null;
    if (value.length < 8) return 'Use at least 8 characters';
    if (value.length > 128) return 'Maximum 128 characters';
    return null;
  }

  String? _validateConfirm(String? v) {
    if (v != _passwordCtrl.text) return 'Passwords do not match';
    return null;
  }

  String? _validateName(String? v) {
    final value = v?.trim() ?? '';
    if (value.isEmpty) return 'Enter a display name';
    if (value.length < 2) return 'At least 2 characters';
    if (value.length > 80) return 'Maximum 80 characters';
    return null;
  }

  Future<void> _submit() async {
    final app = context.read<AppState>();
    app.clearError();
    if (!(_formKey.currentState?.validate() ?? false)) return;

    final ok = _registerMode
        ? await app.signUp(
            displayName: _nameCtrl.text.trim(),
            email: _emailCtrl.text.trim(),
            password: _passwordCtrl.text,
          )
        : await app.signIn(
            email: _emailCtrl.text.trim(),
            password: _passwordCtrl.text,
          );

    if (!mounted) return;
    if (ok) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(builder: (_) => const HomeShell()),
      );
    } else if (app.lastError != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(app.lastError!)),
      );
    }
  }

  Future<void> _guest() async {
    final app = context.read<AppState>();
    app.clearError();
    await app.continueAsGuest();
    if (!mounted) return;
    if (app.session != null) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(builder: (_) => const HomeShell()),
      );
    } else if (app.lastError != null) {
      // Only reach the home shell when the demo sign-in actually succeeded;
      // otherwise surface the error instead of a tokenless, 401-everywhere app.
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(app.lastError!)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final busy = context.watch<AppState>().busy;
    final strength = _strength;

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [AppTheme.greenTint, Colors.white, AppTheme.purpleTint],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Container(
                  padding: const EdgeInsets.all(28),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(28),
                    border: Border.all(
                        color: AppTheme.lightGreen.withValues(alpha: 0.6)),
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.green.withValues(alpha: 0.10),
                        blurRadius: 40,
                        offset: const Offset(0, 16),
                      ),
                    ],
                  ),
                  child: Form(
                    key: _formKey,
                    autovalidateMode: AutovalidateMode.onUserInteraction,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // Brand header -------------------------------------
                        Center(
                          child: Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              gradient: const LinearGradient(
                                colors: [
                                  AppTheme.lightGreen,
                                  AppTheme.lightPurple
                                ],
                              ),
                              borderRadius: BorderRadius.circular(24),
                            ),
                            child: const Icon(
                              Icons.explore_rounded,
                              size: 48,
                              color: AppTheme.green,
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          AppConfig.appName,
                          textAlign: TextAlign.center,
                          style: theme.textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.5,
                          ),
                        ),
                        Text(
                          _registerMode
                              ? 'Create your account'
                              : 'Welcome back, traveller',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: 24),

                        if (_registerMode) ...[
                          TextFormField(
                            controller: _nameCtrl,
                            textInputAction: TextInputAction.next,
                            autofillHints: const [AutofillHints.name],
                            decoration: const InputDecoration(
                              labelText: 'Display name',
                              hintText: 'How should others see you?',
                              prefixIcon: Icon(Icons.person_outline),
                            ),
                            validator: _validateName,
                          ),
                          const SizedBox(height: 12),
                        ],

                        TextFormField(
                          controller: _emailCtrl,
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.next,
                          autofillHints: const [AutofillHints.email],
                          decoration: const InputDecoration(
                            labelText: 'Email',
                            prefixIcon: Icon(Icons.email_outlined),
                          ),
                          validator: _validateEmail,
                        ),
                        const SizedBox(height: 12),

                        TextFormField(
                          controller: _passwordCtrl,
                          obscureText: _obscure,
                          textInputAction: _registerMode
                              ? TextInputAction.next
                              : TextInputAction.done,
                          onChanged: (_) => setState(() {}),
                          onFieldSubmitted: (_) =>
                              _registerMode ? null : _submit(),
                          autofillHints: const [AutofillHints.password],
                          decoration: InputDecoration(
                            labelText: 'Password',
                            prefixIcon: const Icon(Icons.lock_outline),
                            suffixIcon: IconButton(
                              tooltip: _obscure ? 'Show' : 'Hide',
                              onPressed: () =>
                                  setState(() => _obscure = !_obscure),
                              icon: Icon(_obscure
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined),
                            ),
                          ),
                          validator: _validatePassword,
                        ),

                        // Strength meter (register only) -------------------
                        if (_registerMode &&
                            _passwordCtrl.text.isNotEmpty) ...[
                          const SizedBox(height: 10),
                          Row(
                            children: List.generate(4, (i) {
                              final active = i < strength;
                              final color = strength >= 4
                                  ? AppTheme.green
                                  : strength >= 3
                                      ? AppTheme.purple
                                      : AppTheme.danger;
                              return Expanded(
                                child: AnimatedContainer(
                                  duration:
                                      const Duration(milliseconds: 200),
                                  height: 5,
                                  margin: const EdgeInsets.only(right: 6),
                                  decoration: BoxDecoration(
                                    color: active
                                        ? color
                                        : theme.colorScheme
                                            .surfaceContainerHigh,
                                    borderRadius: BorderRadius.circular(99),
                                  ),
                                ),
                              );
                            }),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            const [
                              'Too short',
                              'Weak',
                              'Fair',
                              'Good',
                              'Strong',
                            ][strength],
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: strength >= 4
                                  ? AppTheme.green
                                  : strength >= 3
                                      ? AppTheme.purple
                                      : AppTheme.danger,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],

                        if (_registerMode) ...[
                          const SizedBox(height: 12),
                          TextFormField(
                            controller: _confirmCtrl,
                            obscureText: _obscureConfirm,
                            textInputAction: TextInputAction.done,
                            onFieldSubmitted: (_) => _submit(),
                            decoration: InputDecoration(
                              labelText: 'Confirm password',
                              prefixIcon: const Icon(Icons.lock_reset_outlined),
                              suffixIcon: IconButton(
                                tooltip: _obscureConfirm ? 'Show' : 'Hide',
                                onPressed: () => setState(() =>
                                    _obscureConfirm = !_obscureConfirm),
                                icon: Icon(_obscureConfirm
                                    ? Icons.visibility_outlined
                                    : Icons.visibility_off_outlined),
                              ),
                            ),
                            validator: _validateConfirm,
                          ),
                        ],

                        const SizedBox(height: 24),

                        FilledButton(
                          onPressed: busy ? null : _submit,
                          child: busy
                              ? const SizedBox(
                                  height: 22,
                                  width: 22,
                                  child: CircularProgressIndicator(
                                      strokeWidth: 2),
                                )
                              : Text(_registerMode
                                  ? 'Create account'
                                  : 'Sign in'),
                        ),
                        const SizedBox(height: 8),

                        TextButton(
                          onPressed: busy
                              ? null
                              : () => setState(() {
                                    _registerMode = !_registerMode;
                                    _confirmCtrl.clear();
                                    _formKey.currentState?.reset();
                                  }),
                          child: Text(
                            _registerMode
                                ? 'Already have an account? Sign in'
                                : 'New here? Create an account',
                          ),
                        ),
                        const SizedBox(height: 4),

                        OutlinedButton.icon(
                          onPressed: busy ? null : _guest,
                          style: OutlinedButton.styleFrom(
                            foregroundColor: AppTheme.purple,
                            side: const BorderSide(color: AppTheme.lightPurple),
                          ),
                          icon: const Icon(Icons.rocket_launch_outlined),
                          label: const Text('Explore demo'),
                        ),
                        const SizedBox(height: 12),

                        // Trust strip --------------------------------------
                        Wrap(
                          alignment: WrapAlignment.center,
                          spacing: 14,
                          children: const [
                            _TrustItem(
                                icon: Icons.verified_user_outlined,
                                label: 'Verified community'),
                            _TrustItem(
                                icon: Icons.lock_outline, label: 'Encrypted'),
                          ],
                        ),

                        if (AppConfig.useMocks) ...[
                          const SizedBox(height: 12),
                          Text(
                            'Demo mode: data is stored in memory only and '
                            'resets on restart.',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.outline,
                            ),
                          ),
                        ],
                      ],
                    ),
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

class _TrustItem extends StatelessWidget {
  const _TrustItem({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: AppTheme.green),
        const SizedBox(width: 4),
        Text(
          label,
          style: theme.textTheme.bodySmall
              ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
      ],
    );
  }
}
