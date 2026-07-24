import SwiftUI

@main
struct MeantByMeHeadsetApp: App {
    @StateObject private var companion = CompanionViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(companion)
        }
    }
}
