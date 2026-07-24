import Foundation
import VisionHeadsetOpenSDK

enum CapturePurpose: Equatable {
    case expression
    case command
}

struct EarbudCapture {
    let purpose: CapturePurpose
    let pcm: Data
    let primaryTranscript: String
}

final class ViaimHeadsetService: NSObject, ObservableObject {
    @Published private(set) var status = "尚未连接"
    @Published private(set) var connected = false
    @Published private(set) var recording = false

    var onPrimaryFinal: ((String, CapturePurpose) -> Void)?
    var onCaptureFinished: ((EarbudCapture) -> Void)?
    var onSafetyInterruption: ((String) -> Void)?

    private let manager = VHOManager.shared()
    private let captureQueue = DispatchQueue(label: "cn.meantbyme.viaim.capture")
    private var pcm = Data()
    private var primaryFinals: [String] = []
    private var purpose: CapturePurpose = .expression

    override init() {
        super.init()
        manager.openLog(false)
        manager.delegate = self
        manager.recordDelegate = self
        manager.config.textStream.enabled = true
        manager.config.textStream.enablePartialResult = true
        manager.config.deviceVerifyPolicy = .auto
    }

    func initializeAndConnect() {
        guard
            let key = Bundle.main.object(forInfoDictionaryKey: "VIAIMAppKey") as? String,
            let secret = Bundle.main.object(forInfoDictionaryKey: "VIAIMAppSecret") as? String,
            !key.isEmpty,
            !secret.isEmpty,
            key != "replace_me",
            secret != "replace_me"
        else {
            status = "缺少 Viaim AppKey/AppSecret"
            return
        }
        status = "正在验证 Viaim SDK…"
        manager.initialize(withAppKey: key, appSecret: secret) { [weak self] success, _, error in
            DispatchQueue.main.async {
                guard let self else { return }
                if success {
                    self.status = "SDK 已就绪，正在连接耳机…"
                    self.manager.connectDevice()
                } else {
                    self.status = "SDK 验证失败：\(error?.localizedDescription ?? "未知错误")"
                }
            }
        }
    }

    func startCapture(_ purpose: CapturePurpose) {
        guard connected, !recording else { return }
        captureQueue.sync {
            self.pcm.removeAll(keepingCapacity: true)
            self.primaryFinals.removeAll(keepingCapacity: true)
            self.purpose = purpose
        }
        manager.recordDelegate = self
        manager.start(.live)
    }

    func stopCapture() {
        guard recording else { return }
        manager.stop(.live)
    }
}

extension ViaimHeadsetService: VisionHeadsetDelegate {
    func visionHeadsetBluetoothStatusDidChanged(_ status: VisionHeadsetBluetoothStatus) {}
    func visionHeadsetClassicBluetoothConnectStatusDidChanged(_ connected: Bool) {}

    func visionHeadsetConnectionWillStart() {
        DispatchQueue.main.async { self.status = "正在连接 Viaim 耳机…" }
    }

    func visionHeadsetConnectionDidSucceed() {
        DispatchQueue.main.async {
            self.connected = true
            self.status = "Viaim 耳机已连接"
        }
    }

    func visionHeadsetConnectionDidFailWithError(_ error: Error) {
        DispatchQueue.main.async {
            self.connected = false
            self.status = "连接失败：\(error.localizedDescription)"
        }
    }

    func visionHeadsetConnectionDidDisconnect() {
        captureQueue.sync {
            pcm.removeAll(keepingCapacity: false)
            primaryFinals.removeAll(keepingCapacity: false)
        }
        DispatchQueue.main.async {
            self.connected = false
            self.recording = false
            self.status = "耳机已断开，会话不会自动确认"
            self.onSafetyInterruption?("耳机连接已断开")
        }
    }

    func visionHeadsetCallStatusDidChanged() {}
    func visionHeadsetDeviceInformationDidChanged() {}
}

extension ViaimHeadsetService: VHORecordDelegate {
    func visionHeadsetStartRecordStatus(
        _ success: Bool,
        type: VisionHeadsetRecordType,
        error: Error?
    ) {
        DispatchQueue.main.async {
            self.recording = success
            self.status = success
                ? "正在通过耳机聆听…"
                : "耳机录音启动失败：\(error?.localizedDescription ?? "未知错误")"
        }
    }

    func visionHeadsetStopRecordStatus(
        _ success: Bool,
        type: VisionHeadsetRecordType,
        error: Error?
    ) {
        let capture: EarbudCapture? = captureQueue.sync {
            guard success else { return nil }
            let completed = EarbudCapture(
                purpose: purpose,
                pcm: pcm,
                primaryTranscript: primaryFinals.joined(separator: " ").trimmingCharacters(in: .whitespacesAndNewlines)
            )
            pcm.removeAll(keepingCapacity: false)
            primaryFinals.removeAll(keepingCapacity: false)
            return completed
        }
        DispatchQueue.main.async {
            self.recording = false
            if let capture {
                self.onCaptureFinished?(capture)
            } else {
                self.status = "录音结束失败：\(error?.localizedDescription ?? "未知错误")"
            }
        }
    }

    func visionHeadsetDidReceivedAudioData(_ audioData: VisionHeadsetAudioData) {
        guard audioData.channel == .microphone else { return }
        let data = audioData.data
        captureQueue.async {
            self.pcm.append(data)
        }
    }

    func visionHeadsetRecordBeInterrupted(_ type: VisionHeadsetRecordType) {
        captureQueue.sync {
            pcm.removeAll(keepingCapacity: false)
            primaryFinals.removeAll(keepingCapacity: false)
        }
        DispatchQueue.main.async {
            self.recording = false
            self.status = "耳机录音被中断；不会执行确认或外放"
            self.onSafetyInterruption?("耳机录音被系统中断")
        }
    }

    func vhoTextStreamDidStart(_ type: VisionHeadsetRecordType) {}

    func vhoDidReceiveTextStreamResult(_ result: VHOTextStreamResult) {
        guard
            result.channel == .microphone,
            result.type == .final,
            !result.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else { return }
        let text = result.text
        let currentPurpose = captureQueue.sync { () -> CapturePurpose in
            primaryFinals.append(text)
            return purpose
        }
        DispatchQueue.main.async {
            self.onPrimaryFinal?(text, currentPurpose)
        }
    }

    func vhoTextStreamDidEnd(_ type: VisionHeadsetRecordType, error: Error?) {}

    func vhoTextStreamDidFail(toStart type: VisionHeadsetRecordType, error: Error) {
        DispatchQueue.main.async {
            self.status = "文字流不可用：\(error.localizedDescription)"
        }
    }
}
