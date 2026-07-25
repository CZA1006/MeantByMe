import Foundation
import VisionHeadsetOpenSDK

enum CapturePurpose: Equatable {
    case expression
    case question
    case command
}

struct EarbudCapture {
    let sessionID: String
    let purpose: CapturePurpose
    let pcm: Data
    let primaryTranscript: String
}

final class ViaimHeadsetService: NSObject, ObservableObject {
    @Published private(set) var status = "尚未连接"
    @Published private(set) var connected = false
    @Published private(set) var recording = false

    var onPrimaryFinal: ((String, CapturePurpose) -> Void)?
    var onSpeechActivity: ((CapturePurpose) -> Void)?
    var onCaptureFinished: ((EarbudCapture) -> Void)?
    var onSafetyInterruption: ((String) -> Void)?

    private let manager = VHOManager.shared()
    private let captureQueue = DispatchQueue(label: "cn.meantbyme.viaim.capture")
    private var pcm = Data()
    private var primaryFinals: [String] = []
    private var purpose: CapturePurpose = .expression
    private var captureSessionID = ""
    private var lastEnergyActivityAt: TimeInterval = 0
    private var firstSpeechByteOffset: Int?
    private var lastSpeechByteOffset: Int?
    private var discardRequested = false
    private var discardCompletion: (() -> Void)?
    private var captureStarting = false

    override init() {
        super.init()
#if DEBUG
        manager.openLog(true)
#else
        manager.openLog(false)
#endif
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
                    self.status = self.sdkVerificationFailureMessage(error)
                }
            }
        }
    }

    func startCapture(_ purpose: CapturePurpose, sessionID: String) {
        guard connected, !recording, !captureStarting else { return }
        let callStatus = manager.callStatusEntity.status
        guard
            callStatus != .comming,
            callStatus != .conneted
        else {
            let message = "Viaim 耳机仍处于通话状态，请结束电话或语音通话后重试"
            status = message
            onSafetyInterruption?(message)
            return
        }
        captureQueue.sync {
            self.pcm.removeAll(keepingCapacity: true)
            self.primaryFinals.removeAll(keepingCapacity: true)
            self.purpose = purpose
            self.captureSessionID = sessionID
            self.lastEnergyActivityAt = 0
            self.firstSpeechByteOffset = nil
            self.lastSpeechByteOffset = nil
            self.discardRequested = false
        }
        captureStarting = true
        status = "正在启动耳机聆听…"
        manager.recordDelegate = self
        manager.start(.live)
    }

    func stopCapture() {
        guard recording else { return }
        manager.stop(.live)
    }

    /// Stops the SDK stream and drops all buffered PCM/text without emitting a
    /// capture. The completion runs after the SDK stop callback, so callers can
    /// safely start a fresh expression round without overlapping recordings.
    func discardCurrentCapture(completion: @escaping () -> Void) {
        captureQueue.sync {
            discardRequested = true
            pcm.removeAll(keepingCapacity: false)
            primaryFinals.removeAll(keepingCapacity: false)
            captureSessionID = ""
            firstSpeechByteOffset = nil
            lastSpeechByteOffset = nil
        }
        discardCompletion = completion
        if recording {
            manager.stop(.live)
        } else if !captureStarting {
            finishDiscard()
        }
    }

    private func finishDiscard() {
        let completion = discardCompletion
        discardCompletion = nil
        status = connected ? "本次耳机录音已丢弃" : status
        completion?()
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
            captureSessionID = ""
            firstSpeechByteOffset = nil
            lastSpeechByteOffset = nil
        }
        DispatchQueue.main.async {
            self.connected = false
            self.recording = false
            self.captureStarting = false
            self.status = "耳机已断开，会话不会自动确认"
            self.finishDiscard()
            self.onSafetyInterruption?("耳机连接已断开")
        }
    }

    func visionHeadsetCallStatusDidChanged() {
        let callStatus = manager.callStatusEntity.status
        guard callStatus == .comming || callStatus == .conneted else {
            return
        }
        DispatchQueue.main.async {
            self.status = "Viaim 检测到来电或通话，现场录音不可用"
        }
    }
    func visionHeadsetDeviceInformationDidChanged() {}
}

extension ViaimHeadsetService: VHORecordDelegate {
    func visionHeadsetStartRecordStatus(
        _ success: Bool,
        type: VisionHeadsetRecordType,
        error: Error?
    ) {
        let failureMessage = success ? nil : recordFailureMessage(error)
        if !success {
            captureQueue.sync {
                pcm.removeAll(keepingCapacity: false)
                primaryFinals.removeAll(keepingCapacity: false)
                captureSessionID = ""
                firstSpeechByteOffset = nil
                lastSpeechByteOffset = nil
            }
        }
        DispatchQueue.main.async {
            let shouldDiscard = self.captureQueue.sync {
                self.discardRequested
            }
            self.captureStarting = false
            self.recording = success
            if shouldDiscard {
                if success {
                    self.manager.stop(.live)
                } else {
                    self.finishDiscard()
                }
                return
            }
            self.status = success
                ? "正在通过耳机聆听…"
                : failureMessage ?? "耳机录音启动失败"
            if let failureMessage {
                self.onSafetyInterruption?(failureMessage)
            }
        }
    }

    func visionHeadsetStopRecordStatus(
        _ success: Bool,
        type: VisionHeadsetRecordType,
        error: Error?
    ) {
        let result: (capture: EarbudCapture?, discarded: Bool) =
            captureQueue.sync {
            let discarded = discardRequested
            guard success, !discarded else {
                pcm.removeAll(keepingCapacity: false)
                primaryFinals.removeAll(keepingCapacity: false)
                captureSessionID = ""
                firstSpeechByteOffset = nil
                lastSpeechByteOffset = nil
                discardRequested = false
                return (nil, discarded)
            }
            let speechPCM = Self.pcmAroundDetectedSpeech(
                pcm,
                firstSpeechByteOffset: firstSpeechByteOffset,
                lastSpeechByteOffset: lastSpeechByteOffset
            )
            let completed = EarbudCapture(
                sessionID: captureSessionID,
                purpose: purpose,
                pcm: speechPCM,
                primaryTranscript: primaryFinals.joined(separator: " ").trimmingCharacters(in: .whitespacesAndNewlines)
            )
            pcm.removeAll(keepingCapacity: false)
            primaryFinals.removeAll(keepingCapacity: false)
            captureSessionID = ""
            firstSpeechByteOffset = nil
            lastSpeechByteOffset = nil
            return (completed, false)
        }
        DispatchQueue.main.async {
            self.captureStarting = false
            self.recording = false
            if result.discarded {
                self.finishDiscard()
            } else if let capture = result.capture {
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
            guard !self.discardRequested else { return }
            let chunkStart = self.pcm.count
            self.pcm.append(data)
            let now = ProcessInfo.processInfo.systemUptime
            guard
                Self.looksLikeSpeech(data),
                now - self.lastEnergyActivityAt >= 0.2
            else {
                return
            }
            self.lastEnergyActivityAt = now
            if self.firstSpeechByteOffset == nil {
                self.firstSpeechByteOffset = chunkStart
            }
            self.lastSpeechByteOffset = self.pcm.count
            let currentPurpose = self.purpose
            DispatchQueue.main.async {
                self.onSpeechActivity?(currentPurpose)
            }
        }
    }

    func visionHeadsetRecordBeInterrupted(_ type: VisionHeadsetRecordType) {
        let wasDiscarding = captureQueue.sync {
            let wasDiscarding = discardRequested
            pcm.removeAll(keepingCapacity: false)
            primaryFinals.removeAll(keepingCapacity: false)
            captureSessionID = ""
            firstSpeechByteOffset = nil
            lastSpeechByteOffset = nil
            discardRequested = false
            return wasDiscarding
        }
        DispatchQueue.main.async {
            self.captureStarting = false
            self.recording = false
            self.status = "耳机录音被中断；不会执行确认或外放"
            if wasDiscarding {
                self.finishDiscard()
            }
            self.onSafetyInterruption?("耳机录音被系统中断")
        }
    }

    func vhoTextStreamDidStart(_ type: VisionHeadsetRecordType) {}

    func vhoDidReceiveTextStreamResult(_ result: VHOTextStreamResult) {
        let trimmedText = result.text.trimmingCharacters(
            in: .whitespacesAndNewlines
        )
        guard
            result.channel == .microphone,
            !trimmedText.isEmpty
        else { return }
        let currentPurpose = captureQueue.sync { () -> CapturePurpose? in
            guard !discardRequested else { return nil }
            if firstSpeechByteOffset == nil {
                firstSpeechByteOffset = 0
            }
            lastSpeechByteOffset = pcm.count
            if result.type == .final {
                primaryFinals.append(trimmedText)
            }
            return purpose
        }
        guard let currentPurpose else { return }
        DispatchQueue.main.async {
            self.onSpeechActivity?(currentPurpose)
            if result.type == .final {
                self.onPrimaryFinal?(trimmedText, currentPurpose)
            }
        }
    }

    func vhoTextStreamDidEnd(_ type: VisionHeadsetRecordType, error: Error?) {}

    func vhoTextStreamDidFail(toStart type: VisionHeadsetRecordType, error: Error) {
        DispatchQueue.main.async {
            self.status = "文字流不可用：\(error.localizedDescription)"
        }
    }

    private func recordFailureMessage(_ error: Error?) -> String {
        guard let error else {
            return "耳机录音启动失败：未知错误"
        }
        let code = (error as NSError).code
        switch code {
        case 1501:
            return "Viaim 设备连接已断开，请重新连接耳机"
        case 1502:
            return "当前没有可录制的通话"
        case 1503:
            return "Viaim 判断耳机仍在通话中；请结束电话、FaceTime或语音通话后重试"
        case 1504:
            return "Viaim 已有一段录音正在进行，请稍后重试"
        case 1505:
            return "Viaim 正在下载闪录，完成后才能开始现场录音"
        default:
            return "耳机录音启动失败（错误码 \(code)）：\(error.localizedDescription)"
        }
    }

    private func sdkVerificationFailureMessage(_ error: Error?) -> String {
        guard let error else {
            return "SDK 验证失败：未知错误"
        }
        let nsError = error as NSError
        if (
            nsError.domain == NSURLErrorDomain
            && nsError.code == NSURLErrorNotConnectedToInternet
        ) {
            return "iPhone 已阻止 MeantByMe 访问网络。请在“设置”中允许本 App 使用无线局域网与蜂窝数据，再重试 Viaim 验证。"
        }
        if nsError.domain == NSURLErrorDomain {
            switch nsError.code {
            case NSURLErrorCannotFindHost:
                return "无法解析 Viaim 验证服务器，请检查 DNS、VPN 或代理设置。"
            case NSURLErrorCannotConnectToHost:
                return "无法连接 Viaim 验证服务器，请检查网络、防火墙或 VPN。"
            case NSURLErrorTimedOut:
                return "连接 Viaim 验证服务器超时，请切换网络后重试。"
            default:
                break
            }
        }
        return "SDK 验证失败：\(error.localizedDescription)"
    }

    /// Lightweight local VAD so unclear speech still starts the silence timer
    /// even when the SDK cannot produce a partial transcript.
    private static func looksLikeSpeech(_ data: Data) -> Bool {
        guard data.count >= 2 else { return false }
        var squaredTotal = 0.0
        var sampleCount = 0
        data.withUnsafeBytes { rawBuffer in
            let bytes = rawBuffer.bindMemory(to: UInt8.self)
            var index = 0
            while index + 1 < bytes.count {
                let bits = UInt16(bytes[index])
                    | (UInt16(bytes[index + 1]) << 8)
                let sample = Double(Int16(bitPattern: bits))
                squaredTotal += sample * sample
                sampleCount += 1
                index += 2
            }
        }
        guard sampleCount > 0 else { return false }
        let rootMeanSquare = sqrt(squaredTotal / Double(sampleCount))
        return rootMeanSquare >= 450
    }

    /// The silence window determines when an expression ends, but it must not
    /// be uploaded as part of the ASR clip. Preserve a small amount of context
    /// around detected speech so word boundaries are not cut.
    private static func pcmAroundDetectedSpeech(
        _ data: Data,
        firstSpeechByteOffset: Int?,
        lastSpeechByteOffset: Int?
    ) -> Data {
        guard
            let firstSpeechByteOffset,
            let lastSpeechByteOffset,
            firstSpeechByteOffset <= lastSpeechByteOffset
        else {
            return data
        }
        let bytesPerSecond = 16_000 * 2
        let leadingPadding = bytesPerSecond / 4
        let trailingPadding = bytesPerSecond / 2
        let lowerBound = max(
            0,
            firstSpeechByteOffset - leadingPadding
        ) & ~1
        let upperBound = min(
            data.count,
            lastSpeechByteOffset + trailingPadding
        ) & ~1
        guard lowerBound < upperBound else {
            return data
        }
        return data.subdata(in: lowerBound..<upperBound)
    }
}
