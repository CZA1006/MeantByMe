@preconcurrency import AVFoundation
import Foundation

enum AudioRouterError: LocalizedError {
    case earbudsNotActive

    var errorDescription: String? {
        "未检测到耳机私密输出，为防止未确认内容外放，已停止朗读。"
    }
}

@MainActor
final class AudioRouter: NSObject {
    private let speech = AVSpeechSynthesizer()
    private var player: AVAudioPlayer?
    private var completion: ((Bool) -> Void)?

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
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playback, mode: .spokenAudio)
        try session.overrideOutputAudioPort(.speaker)
        try session.setActive(true)
        self.completion = completion
        player = try AVAudioPlayer(data: data)
        player?.delegate = self
        player?.prepareToPlay()
        player?.play()
    }

    func stop() {
        speech.stopSpeaking(at: .immediate)
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
