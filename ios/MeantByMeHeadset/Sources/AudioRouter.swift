@preconcurrency import AVFoundation
import Foundation

enum AudioRouterError: LocalizedError {
    case earbudsNotActive
    case publicSpeakerNotActive
    case playbackCouldNotStart

    var errorDescription: String? {
        switch self {
        case .earbudsNotActive:
            return "未检测到耳机私密输出，为防止未确认内容外放，已停止朗读。"
        case .publicSpeakerNotActive:
            return "无法切换到 iPhone 扬声器，本次确认内容没有外放。"
        case .playbackCouldNotStart:
            return "音频播放器启动失败，本次确认内容没有外放。"
        }
    }
}

@MainActor
final class AudioRouter: NSObject {
    private let speech = AVSpeechSynthesizer()
    private let speakerTestSpeech = AVSpeechSynthesizer()
    private var player: AVAudioPlayer?
    private var completion: ((Bool) -> Void)?
    private var speakerTestActive = false

    override init() {
        super.init()
        speech.delegate = self
    }

    func playPrivateText(
        _ text: String,
        language: String,
        completion: @escaping (Bool) -> Void
    ) throws {
        try configurePrivateRoute()
        self.completion = completion
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(
            language: language.hasPrefix("zh") ? "zh-CN" : "en-US"
        )
        utterance.rate = 0.43
        speech.speak(utterance)
    }

    func playPrivateAudio(
        _ data: Data,
        completion: @escaping (Bool) -> Void
    ) throws {
        try configurePrivateRoute()
        self.completion = completion
        player = try AVAudioPlayer(data: data)
        player?.delegate = self
        player?.prepareToPlay()
        player?.play()
    }

    func playPublicAudio(
        _ data: Data,
        completion: @escaping (Bool) -> Void
    ) throws {
        try configurePublicRoute()
        self.completion = completion
        player = try AVAudioPlayer(data: data)
        player?.delegate = self
        player?.volume = 1
        guard
            player?.prepareToPlay() == true
        else {
            player = nil
            self.completion = nil
            deactivateAudioSession()
            throw AudioRouterError.playbackCouldNotStart
        }
        // Viaim may release its HFP recording route immediately after the
        // command capture callback. Let that route change settle, then apply
        // the speaker override once more immediately before playback.
        DispatchQueue.main.asyncAfter(
            deadline: .now() + 0.25
        ) { [weak self] in
            self?.startPublicPlaybackAfterRouteSettles()
        }
    }

    func beginSpeakerVolumeTest() async throws {
        speakerTestSpeech.stopSpeaking(at: .immediate)
        try configurePublicRoute()
        // The Viaim Bluetooth route may take a moment to release. Keep the
        // public route active while the system volume slider is on screen.
        try await Task.sleep(nanoseconds: 300_000_000)
        let session = AVAudioSession.sharedInstance()
        try session.overrideOutputAudioPort(.speaker)
        guard session.currentRoute.outputs.contains(where: {
            $0.portType == .builtInSpeaker
        }) else {
            deactivateAudioSession()
            throw AudioRouterError.publicSpeakerNotActive
        }
        speakerTestActive = true
#if DEBUG
        debugLogRoute("speaker_test", session: session)
#endif
    }

    func playSpeakerVolumeTest() throws {
        guard speakerTestActive else {
            throw AudioRouterError.publicSpeakerNotActive
        }
        let session = AVAudioSession.sharedInstance()
        try session.overrideOutputAudioPort(.speaker)
        guard session.currentRoute.outputs.contains(where: {
            $0.portType == .builtInSpeaker
        }) else {
            throw AudioRouterError.publicSpeakerNotActive
        }
        speakerTestSpeech.stopSpeaking(at: .immediate)
        let utterance = AVSpeechUtterance(
            string: "这是手机扬声器测试，请将音量调节到清晰可听。"
        )
        utterance.voice = AVSpeechSynthesisVoice(language: "zh-CN")
        utterance.rate = 0.43
        utterance.volume = 1
        speakerTestSpeech.speak(utterance)
#if DEBUG
        print(
            "[MeantByMeAudio] playback_started purpose=speaker_test "
                + "system_volume=\(session.outputVolume)"
        )
#endif
    }

    func endSpeakerVolumeTest() {
        speakerTestSpeech.stopSpeaking(at: .immediate)
        speakerTestActive = false
        deactivateAudioSession()
    }

    func stop() {
        speech.stopSpeaking(at: .immediate)
        speakerTestSpeech.stopSpeaking(at: .immediate)
        speakerTestActive = false
        player?.stop()
        player = nil
        completion = nil
        deactivateAudioSession()
    }

    private func configurePrivateRoute() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(
            .playAndRecord,
            mode: .spokenAudio,
            options: [.allowBluetoothHFP, .allowBluetoothA2DP]
        )
        try session.setActive(true)
        try session.overrideOutputAudioPort(.none)
        let privatePorts: Set<AVAudioSession.Port> = [
            .headphones, .bluetoothA2DP, .bluetoothHFP, .bluetoothLE
        ]
        guard session.currentRoute.outputs.contains(where: {
            privatePorts.contains($0.portType)
        }) else {
            throw AudioRouterError.earbudsNotActive
        }
#if DEBUG
        debugLogRoute("private", session: session)
#endif
    }

    private func configurePublicRoute() throws {
        let session = AVAudioSession.sharedInstance()
        try? session.setActive(
            false,
            options: .notifyOthersOnDeactivation
        )
        // `overrideOutputAudioPort(.speaker)` is valid only for
        // `.playAndRecord`; using it with `.playback` returns OSStatus -50.
        try session.setCategory(
            .playAndRecord,
            mode: .default,
            options: [.defaultToSpeaker]
        )
        try session.setActive(true)
        try session.overrideOutputAudioPort(.speaker)
    }

    private func startPublicPlaybackAfterRouteSettles() {
        guard let player, completion != nil else { return }
        let session = AVAudioSession.sharedInstance()
        do {
            try session.overrideOutputAudioPort(.speaker)
            guard session.currentRoute.outputs.contains(where: {
                $0.portType == .builtInSpeaker
            }) else {
                throw AudioRouterError.publicSpeakerNotActive
            }
#if DEBUG
            debugLogRoute("public", session: session)
#endif
            guard player.play() else {
                throw AudioRouterError.playbackCouldNotStart
            }
#if DEBUG
            print(
                "[MeantByMeAudio] playback_started purpose=public "
                    + "player_volume=\(player.volume) "
                    + "system_volume=\(session.outputVolume)"
            )
#endif
        } catch {
#if DEBUG
            let nsError = error as NSError
            print(
                "[MeantByMeAudio] public_playback_failed "
                    + "domain=\(nsError.domain) code=\(nsError.code)"
            )
#endif
            finish(false)
        }
    }

    private func finish(_ success: Bool) {
        let callback = completion
        completion = nil
        player = nil
        deactivateAudioSession()
        callback?(success)
    }

    private func deactivateAudioSession() {
        try? AVAudioSession.sharedInstance().setActive(
            false,
            options: .notifyOthersOnDeactivation
        )
    }

#if DEBUG
    private func debugLogRoute(
        _ purpose: String,
        session: AVAudioSession
    ) {
        let outputs = session.currentRoute.outputs
            .map(\.portType.rawValue)
            .joined(separator: ",")
        print(
            "[MeantByMeAudio] route purpose=\(purpose) "
                + "outputs=\(outputs) "
                + "system_volume=\(session.outputVolume)"
        )
    }
#endif
}

extension AudioRouter: @preconcurrency AVAudioPlayerDelegate {
    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        finish(flag)
    }

    func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
        finish(false)
    }
}

extension AudioRouter: @preconcurrency AVSpeechSynthesizerDelegate {
    func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didFinish utterance: AVSpeechUtterance
    ) {
        finish(true)
    }

    func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didCancel utterance: AVSpeechUtterance
    ) {
        finish(false)
    }
}
