/// Local, rule-based companion responder.
///
/// IMPORTANT: there is NO AI/ML backend wired yet (the `ai-ml` workstream is a
/// separate, unverified contract). This class is a stand-in so the chat screen
/// is fully explorable in the demo. It produces deterministic, safety-aware
/// replies from simple keyword rules — it is not a real model. When a real
/// `/ai/chat` contract is agreed with Laptop 3, replace the body of [reply]
/// with an HTTP call; the chat UI needs no changes.
class CompanionService {
  const CompanionService();

  Future<String> reply(String userText) async {
    await Future<void>.delayed(const Duration(milliseconds: 600));
    final text = userText.toLowerCase().trim();

    if (text.isEmpty) {
      return "I'm here with you. Tell me where you are or what's happening.";
    }
    if (_containsAny(text, ['sos', 'emergency', 'help me', 'danger', 'scared'])) {
      return "I'm right here. If you're in immediate danger, tap the red SOS "
          "button on the Safe Mode screen — it records an incident with your "
          "location. Would you like me to walk you through it?";
    }
    if (_containsAny(text, ['safe', 'safe mode'])) {
      return "Safe Mode arms your trip: it keeps an eye on your check-ins and "
          "puts SOS one tap away. You can start it from the Safe Mode tab.";
    }
    if (_containsAny(text, ['check-in', 'check in', 'checkin', 'back by'])) {
      return "Setting a check-in is a good idea — pick a time you expect to be "
          "somewhere, and if you don't mark yourself safe, it stays visible. "
          "Open the Check-ins screen to create one.";
    }
    if (_containsAny(text, ['contact', 'family', 'friend', 'trusted'])) {
      return "Your trusted contacts live in the Contacts tab. They're the "
          "people you'd want reachable in an emergency. You can add them there.";
    }
    if (_containsAny(text, ['area', 'neighborhood', 'neighbourhood', 'report',
        'lighting', 'harassment', 'poech', 'unsafe'])) {
      return "You can file or browse community safety reports on the Reports "
          "screen — things like poor lighting or suspicious activity near a "
          "place. Reports are about locations, never about people.";
    }
    if (_containsAny(text, ['where', 'map', 'nearby', 'location'])) {
      return "Maps and nearby helpers need the AI/ML and location services, "
          "which aren't wired into this prototype yet. Community reports do "
          "support a nearby search on the backend when it's connected.";
    }
    if (_containsAny(text, ['hello', 'hi', 'hey', 'namaste'])) {
      return "Hello! I'm your Roamlary travel companion. I can help you set "
          "check-ins, reach trusted contacts, and stay aware of your surroundings.";
    }
    if (_containsAny(text, ['thank', 'thanks'])) {
      return "Anytime. Stay safe out there — I'm with you.";
    }

    return "Got it. I can help with check-ins, trusted contacts, Safe Mode, "
        "and community safety reports. What would you like to do?";
  }

  static bool _containsAny(String input, List<String> needles) =>
      needles.any(input.contains);
}
