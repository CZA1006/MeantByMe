@preconcurrency import AVFoundation
import Foundation

enum AudioRouterError: LocalizedError {
    case earbudsNotActive
    case publicSpeakerNotActive
    case invalidAudioData
    case playbackCouldNotStart

    var errorDescription: String? {
        switch self {
        case .earbudsNotActive:
            return "未检测到耳机私密输出，为防止未确认内容外放，已停止朗读。"
        case .publicSpeakerNotActive:
            return "无法切换到 iPhone 扬声器，本次确认内容没有外放。"
        case .invalidAudioData:
            return "收到的音频为空或无法解码，本次内容没有播放。"
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
        let trimmedText = text.trimmingCharacters(
            in: .whitespacesAndNewlines
        )
        guard
            !trimmedText.isEmpty,
            let voice = AVSpeechSynthesisVoice(
                language: language.hasPrefix("zh") ? "zh-CN" : "en-US"
            )
        else {
            throw AudioRouterError.playbackCouldNotStart
        }
        try configurePrivateRoute()
        self.completion = completion
        let utterance = AVSpeechUtterance(string: trimmedText)
        utterance.voice = voice
        utterance.rate = 0.43
        speech.speak(utterance)
    }

    func playPrivateAudio(
        _ data: Data,
        completion: @escaping (Bool) -> Void
    ) throws {
        guard !data.isEmpty else {
            throw AudioRouterError.invalidAudioData
        }
        try configurePrivateRoute()
        self.completion = completion
        do {
            player = try makePlayer(data: data)
        } catch {
            cancelSynchronousPlaybackStart()
            throw error
        }
        guard player?.play() == true else {
            cancelSynchronousPlaybackStart()
            throw AudioRouterError.playbackCouldNotStart
        }
    }

    func playPublicAudio(
        _ data: Data,
        completion: @escaping (Bool) -> Void
    ) throws {
        guard !data.isEmpty else {
            throw AudioRouterError.invalidAudioData
        }
        try configurePublicRoute()
        self.completion = completion
        do {
            player = try makePlayer(data: data)
        } catch {
            cancelSynchronousPlaybackStart()
            throw error
        }
        player?.volume = 1
        // Viaim may release its HFP recording route immediately after the
        // command capture callback. Let that route change settle, then apply
        // the speaker override once more immediately before playback.
        DispatchQueue.main.asyncAfter(
            deadline: .now() + 0.25
        ) { [weak self] in
            self?.startPublicPlaybackAfterRouteSettles()
        }
    }

    func playPublicText(
        _ text: String,
        language: String,
        completion: @escaping (Bool) -> Void
    ) throws {
        let trimmedText = text.trimmingCharacters(
            in: .whitespacesAndNewlines
        )
        guard
            !trimmedText.isEmpty,
            let voice = AVSpeechSynthesisVoice(
                language: language.hasPrefix("zh") ? "zh-CN" : "en-US"
            )
        else {
            throw AudioRouterError.playbackCouldNotStart
        }
        try configurePublicRoute()
        self.completion = completion
        let utterance = AVSpeechUtterance(string: trimmedText)
        utterance.voice = voice
        utterance.rate = 0.43
        utterance.volume = 1
        DispatchQueue.main.asyncAfter(
            deadline: .now() + 0.25
        ) { [weak self] in
            self?.startPublicSpeechAfterRouteSettles(utterance)
        }
    }

    func beginSpeakerVolumeTest() async throws {
        if speakerTestSpeech.isSpeaking {
            speakerTestSpeech.stopSpeaking(at: .immediate)
        }
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
        guard session.outputVolume > 0.001 else {
#if DEBUG
            print(
                "[MeantByMeAudio] playback_skipped purpose=speaker_test "
                    + "reason=system_volume_zero"
            )
#endif
            return
        }
        if speakerTestSpeech.isSpeaking {
            speakerTestSpeech.stopSpeaking(at: .immediate)
        }
        let utterance = AVSpeechUtterance(
            string: "这是手机扬声器测试，请将音量调节到清晰可听。"
        )
        guard let voice = AVSpeechSynthesisVoice(language: "zh-CN") else {
            throw AudioRouterError.playbackCouldNotStart
        }
        utterance.voice = voice
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
        if speech.isSpeaking {
            speech.stopSpeaking(at: .immediate)
        }
        if speakerTestSpeech.isSpeaking {
            speakerTestSpeech.stopSpeaking(at: .immediate)
        }
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
            deactivateAudioSession()
            throw AudioRouterError.earbudsNotActive
        }
#if DEBUG
        debugLogRoute("private", session: session)
#endif
    }

    private func makePlayer(data: Data) throws -> AVAudioPlayer {
        guard !data.isEmpty else {
            throw AudioRouterError.invalidAudioData
        }
        let decodedPlayer: AVAudioPlayer
        do {
            decodedPlayer = try AVAudioPlayer(data: data)
        } catch {
            throw AudioRouterError.invalidAudioData
        }
        guard decodedPlayer.duration > 0 else {
            throw AudioRouterError.invalidAudioData
        }
        decodedPlayer.delegate = self
        guard decodedPlayer.prepareToPlay() else {
            throw AudioRouterError.playbackCouldNotStart
        }
        return decodedPlayer
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

    private func startPublicSpeechAfterRouteSettles(
        _ utterance: AVSpeechUtterance
    ) {
        guard completion != nil else { return }
        let session = AVAudioSession.sharedInstance()
        do {
            try session.overrideOutputAudioPort(.speaker)
            guard session.currentRoute.outputs.contains(where: {
                $0.portType == .builtInSpeaker
            }) else {
                throw AudioRouterError.publicSpeakerNotActive
            }
#if DEBUG
            debugLogRoute("public_text", session: session)
#endif
            speech.speak(utterance)
        } catch {
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

    private func cancelSynchronousPlaybackStart() {
        completion = nil
        player = nil
        deactivateAudioSession()
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

extension AudioRouter: AVAudioPlayerDelegate {
    nonisolated func audioPlayerDidFinishPlaying(
        _ player: AVAudioPlayer,
        successfully flag: Bool
    ) {
        Task { @MainActor [weak self] in
            self?.finish(flag)
        }
    }

    nonisolated func audioPlayerDecodeErrorDidOccur(
        _ player: AVAudioPlayer,
        error: Error?
    ) {
        Task { @MainActor [weak self] in
            self?.finish(false)
        }
    }
}

extension AudioRouter: AVSpeechSynthesizerDelegate {
    nonisolated func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didFinish utterance: AVSpeechUtterance
    ) {
        Task { @MainActor [weak self] in
            self?.finish(true)
        }
    }

    nonisolated func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didCancel utterance: AVSpeechUtterance
    ) {
        Task { @MainActor [weak self] in
            self?.finish(false)
        }
    }
}
