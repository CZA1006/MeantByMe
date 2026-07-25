import Foundation

enum GatewayClientError: LocalizedError {
    case invalidConfiguration
    case invalidResponse
    case incompatibleBackend
    case staleSession
    case server(Int, String)

    var errorDescription: String? {
        switch self {
        case .invalidConfiguration: return "后端地址或访问配置无效"
        case .invalidResponse: return "后端返回了无法识别的数据"
        case .incompatibleBackend:
            return "当前后端版本过旧，不支持新版耳机交互流程。请重新部署 meantbyme-ios 后端。"
        case .staleSession: return "已忽略上一会话的迟到请求"
        case let .server(code, message): return "后端错误 \(code)：\(message)"
        }
    }
}

actor GatewayClient {
    private let baseURL: URL
    private let demoToken: String
    private var sessionId = ""
    private var sessionToken = ""

    init(bundle: Bundle = .main) throws {
        guard
            let value = bundle.object(forInfoDictionaryKey: "MeantByMeBaseURL") as? String,
            let url = URL(string: value),
            let token = bundle.object(forInfoDictionaryKey: "MeantByMeDemoToken") as? String,
            !token.isEmpty
        else { throw GatewayClientError.invalidConfiguration }
        baseURL = url
        demoToken = token
    }

    func createSession(
        language: String = "zh",
        profileRef: String = "lin_yue_demo"
    ) async throws -> DemoResponse {
        let body = try JSONSerialization.data(withJSONObject: [
            "language": language,
            "profile_ref": profileRef,
        ])
        let response: DemoResponse = try await request(
            path: "/api/sessions",
            method: "POST",
            contentType: "application/json",
            body: body,
            includeSession: false
        )
        guard let token = response.sessionToken else {
#if DEBUG
            print(
                "[MeantByMeGateway] semantic_invalid "
                    + "path=/api/sessions missing=session_token"
            )
#endif
            throw GatewayClientError.invalidResponse
        }
        sessionId = response.session.sessionId
        sessionToken = token
        return response
    }

    func createQASession(
        language: String = "zh",
        profileRef: String = "lin_yue_demo"
    ) async throws -> QASessionResponse {
        let body = try JSONSerialization.data(withJSONObject: [
            "language": language,
            "profile_ref": profileRef,
        ])
        let response: QASessionResponse = try await request(
            path: "/api/qa/sessions",
            method: "POST",
            contentType: "application/json",
            body: body,
            includeSession: false
        )
        guard let token = response.sessionToken else {
#if DEBUG
            print(
                "[MeantByMeGateway] semantic_invalid "
                    + "path=/api/qa/sessions missing=session_token"
            )
#endif
            throw GatewayClientError.invalidResponse
        }
        sessionId = response.sessionId
        sessionToken = token
        return response
    }

    func listProfiles() async throws -> [UserProfileSummary] {
        let response: ProfilesResponse = try await request(
            path: "/api/profiles",
            method: "GET",
            contentType: "application/json",
            body: nil,
            includeSession: false
        )
        return response.profiles
    }

    func profileDetail(
        profileRef: String
    ) async throws -> UserProfileDetail {
        let response: ProfileDetailResponse = try await request(
            path: "/api/profiles/\(profileRef)",
            method: "GET",
            contentType: "application/json",
            body: nil,
            includeSession: false
        )
        return response.profile
    }

    func createProfile(
        _ input: NewUserProfileInput
    ) async throws -> UserProfileSummary {
        let body = try JSONEncoder().encode(input)
        let response: ProfileSummaryResponse = try await request(
            path: "/api/profiles/questionnaire",
            method: "POST",
            contentType: "application/json",
            body: body,
            includeSession: false
        )
        return response.profile
    }

    func importProfileMarkdown(
        _ markdown: Data
    ) async throws -> UserProfileSummary {
        let response: ProfileSummaryResponse = try await request(
            path: "/api/profiles",
            method: "POST",
            contentType: "text/markdown",
            body: markdown,
            includeSession: false
        )
        return response.profile
    }

    func uploadExpression(wav: Data, primaryTranscript: String) async throws {
        debugLogWAVUpload(
            kind: "expression",
            wav: wav,
            hasPrimaryTranscript: !primaryTranscript.isEmpty
        )
        let url = baseURL.appendingPathComponent(
            "/api/sessions/\(sessionId)/audio"
        )
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.httpBody = wav
        request.setValue("audio/wav", forHTTPHeaderField: "Content-Type")
        if !primaryTranscript.isEmpty {
            request.setValue(
                Data(primaryTranscript.utf8).base64EncodedString(),
                forHTTPHeaderField: "X-Viaim-Primary-Transcript-B64"
            )
        }
        addHeaders(to: &request, includeSession: true)
        let (data, response) = try await perform(request)
        try validate(response: response, data: data)
    }

    func command(
        _ command: String,
        payload: [String: Any] = [:],
        confirmationMethod: String? = nil,
        expectedSessionID: String? = nil
    ) async throws -> DemoResponse {
        if let expectedSessionID, expectedSessionID != sessionId {
            throw GatewayClientError.staleSession
        }
        let object: [String: Any?] = [
            "command": command,
            "payload": payload,
            "confirmation_method": confirmationMethod,
        ]
        let body = try JSONSerialization.data(
            withJSONObject: object.compactMapValues { $0 }
        )
        return try await request(
            path: "/api/sessions/\(sessionId)/commands",
            method: "POST",
            contentType: "application/json",
            body: body
        )
    }

    func interpretCommand(
        wav: Data,
        primaryTranscript: String,
        promptID: String
    ) async throws -> EarbudInterpretation {
        debugLogWAVUpload(
            kind: "command",
            wav: wav,
            hasPrimaryTranscript: !primaryTranscript.isEmpty
        )
        let url = baseURL.appendingPathComponent(
            "/api/sessions/\(sessionId)/earbud/interpret"
        )
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.httpBody = wav
        request.setValue("audio/wav", forHTTPHeaderField: "Content-Type")
        request.setValue(
            Data(primaryTranscript.utf8).base64EncodedString(),
            forHTTPHeaderField: "X-Viaim-Primary-Transcript-B64"
        )
        request.setValue(
            promptID,
            forHTTPHeaderField: "X-MeantByMe-Prompt-ID"
        )
        addHeaders(to: &request, includeSession: true)
        let (data, response) = try await perform(request)
        try validate(response: response, data: data)
        do {
            return try JSONDecoder().decode(EarbudInterpretation.self, from: data)
        } catch {
            Self.debugLogDecodeFailure(
                error,
                data: data,
                path: url.path,
                expectedType: EarbudInterpretation.self
            )
            throw GatewayClientError.invalidResponse
        }
    }

    func audio(kind: String) async throws -> Data {
        let url = baseURL.appendingPathComponent(
            "/api/sessions/\(sessionId)/audio/\(kind)"
        )
        var request = URLRequest(url: url)
        addHeaders(to: &request, includeSession: true)
        let (data, response) = try await perform(request)
        try validate(response: response, data: data)
        return data
    }

    func askAI(
        wav: Data,
        primaryTranscript: String,
        turnID: String,
        expectedSessionID: String
    ) async throws -> QASessionResponse {
        guard expectedSessionID == sessionId else {
            throw GatewayClientError.staleSession
        }
        debugLogWAVUpload(
            kind: "qa",
            wav: wav,
            hasPrimaryTranscript: !primaryTranscript.isEmpty
        )
        let url = baseURL.appendingPathComponent(
            "/api/qa/sessions/\(sessionId)/turns/\(turnID)"
        )
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.httpBody = wav
        request.setValue("audio/wav", forHTTPHeaderField: "Content-Type")
        if !primaryTranscript.isEmpty {
            request.setValue(
                Data(primaryTranscript.utf8).base64EncodedString(),
                forHTTPHeaderField: "X-Viaim-Primary-Transcript-B64"
            )
        }
        addHeaders(to: &request, includeSession: true)
        let (data, response) = try await perform(request)
        try validate(response: response, data: data)
        do {
            return try JSONDecoder().decode(
                QASessionResponse.self, from: data
            )
        } catch {
            Self.debugLogDecodeFailure(
                error,
                data: data,
                path: url.path,
                expectedType: QASessionResponse.self
            )
            throw GatewayClientError.invalidResponse
        }
    }

    func qaAudio(
        turnID: String,
        expectedSessionID: String
    ) async throws -> Data {
        guard expectedSessionID == sessionId else {
            throw GatewayClientError.staleSession
        }
        let url = baseURL.appendingPathComponent(
            "/api/qa/sessions/\(sessionId)/turns/\(turnID)/audio"
        )
        var request = URLRequest(url: url)
        addHeaders(to: &request, includeSession: true)
        let (data, response) = try await perform(request)
        try validate(response: response, data: data)
        return data
    }

    func cancelQATurn(
        turnID: String,
        expectedSessionID: String
    ) async throws -> QASessionResponse {
        guard expectedSessionID == sessionId else {
            throw GatewayClientError.staleSession
        }
        return try await request(
            path: (
                "/api/qa/sessions/\(sessionId)/turns/"
                    + "\(turnID)/cancel"
            ),
            method: "POST",
            contentType: "application/json",
            body: Data("{}".utf8)
        )
    }

    func stopQASession(
        expectedSessionID: String
    ) async throws -> QASessionResponse {
        guard expectedSessionID == sessionId else {
            throw GatewayClientError.staleSession
        }
        return try await request(
            path: "/api/qa/sessions/\(sessionId)/stop",
            method: "POST",
            contentType: "application/json",
            body: Data("{}".utf8)
        )
    }

    private func request<T: Decodable>(
        path: String,
        method: String,
        contentType: String,
        body: Data?,
        includeSession: Bool = true
    ) async throws -> T {
        try await request(
            absoluteURL: baseURL.appendingPathComponent(path),
            method: method,
            contentType: contentType,
            body: body,
            includeSession: includeSession
        )
    }

    private func request<T: Decodable>(
        absoluteURL: URL,
        method: String,
        contentType: String,
        body: Data?,
        includeSession: Bool = true
    ) async throws -> T {
        var request = URLRequest(url: absoluteURL)
        request.httpMethod = method
        request.httpBody = body
        request.setValue(contentType, forHTTPHeaderField: "Content-Type")
        addHeaders(to: &request, includeSession: includeSession)
        let (data, response) = try await perform(request)
        try validate(response: response, data: data)
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            Self.debugLogDecodeFailure(
                error,
                data: data,
                path: absoluteURL.path,
                expectedType: T.self
            )
            throw GatewayClientError.invalidResponse
        }
    }

    private func addHeaders(to request: inout URLRequest, includeSession: Bool) {
        request.setValue(demoToken, forHTTPHeaderField: "X-Demo-Token")
        if includeSession {
            request.setValue(sessionToken, forHTTPHeaderField: "X-Demo-Session")
        }
    }

    private func perform(
        _ request: URLRequest
    ) async throws -> (Data, URLResponse) {
        do {
            return try await URLSession.shared.data(for: request)
        } catch {
#if DEBUG
            let nsError = error as NSError
            print(
                "[MeantByMeGateway] transport_failed "
                    + "method=\(request.httpMethod ?? "<unknown>") "
                    + "path=\(request.url?.path ?? "<unknown>") "
                    + "domain=\(nsError.domain) code=\(nsError.code)"
            )
#endif
            throw error
        }
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
#if DEBUG
            print("[MeantByMeGateway] invalid non-HTTP response")
#endif
            throw GatewayClientError.invalidResponse
        }
#if DEBUG
        let path = http.url?.path ?? "<unknown>"
        print(
            "[MeantByMeGateway] response path=\(path) "
                + "status=\(http.statusCode) bytes=\(data.count)"
        )
#endif
        guard (200..<300).contains(http.statusCode) else {
            let errorPayload = (
                try? JSONSerialization.jsonObject(with: data)
            ) as? [String: Any]
            if (
                http.statusCode == 422
                && Self.isUnsupportedCommandError(errorPayload?["detail"])
            ) {
#if DEBUG
                print(
                    "[MeantByMeGateway] incompatible_backend "
                        + "missing_new_command=true"
                )
#endif
                throw GatewayClientError.incompatibleBackend
            }
            let message = Self.errorDetailMessage(
                errorPayload?["detail"]
            )
#if DEBUG
            print(
                "[MeantByMeGateway] rejected status=\(http.statusCode) "
                    + "detail=\(message)"
            )
#endif
            throw GatewayClientError.server(http.statusCode, message)
        }
    }

    private static func isUnsupportedCommandError(_ detail: Any?) -> Bool {
        guard let errors = detail as? [[String: Any]] else {
            return false
        }
        let newCommands: Set<String> = [
            "proceed_without_heard_confirmation",
            "prepare_candidate_readback",
            "reject_current_candidate",
            "confirm_neutral_playback",
        ]
        return errors.contains { error in
            guard
                error["type"] as? String == "enum",
                let location = error["loc"] as? [String],
                location.contains("command"),
                let input = error["input"] as? String
            else {
                return false
            }
            return newCommands.contains(input)
        }
    }

    private static func errorDetailMessage(_ detail: Any?) -> String {
        if let message = detail as? String {
            return message
        }
        if
            let errors = detail as? [[String: Any]],
            let message = errors.first?["msg"] as? String
        {
            return message
        }
        return "请求失败"
    }

    private static func debugLogDecodeFailure<T>(
        _ error: Error,
        data: Data,
        path: String,
        expectedType: T.Type
    ) {
#if DEBUG
        let reason: String
        switch error {
        case let DecodingError.keyNotFound(key, context):
            reason = (
                "missing_key=\(key.stringValue) "
                    + "coding_path=\(codingPath(context.codingPath))"
            )
        case let DecodingError.typeMismatch(_, context):
            reason = (
                "type_mismatch coding_path="
                    + codingPath(context.codingPath)
                    + " detail=\(context.debugDescription)"
            )
        case let DecodingError.valueNotFound(_, context):
            reason = (
                "missing_value coding_path="
                    + codingPath(context.codingPath)
                    + " detail=\(context.debugDescription)"
            )
        case let DecodingError.dataCorrupted(context):
            reason = (
                "data_corrupted coding_path="
                    + codingPath(context.codingPath)
                    + " detail=\(context.debugDescription)"
            )
        default:
            let nsError = error as NSError
            reason = "domain=\(nsError.domain) code=\(nsError.code)"
        }
        let rootKeys: String
        if
            let object = try? JSONSerialization.jsonObject(with: data),
            let dictionary = object as? [String: Any]
        {
            rootKeys = dictionary.keys.sorted().joined(separator: ",")
        } else {
            rootKeys = "<non-object>"
        }
        print(
            "[MeantByMeGateway] decode_failed "
                + "path=\(path) expected=\(String(describing: expectedType)) "
                + "\(reason) root_keys=\(rootKeys) bytes=\(data.count)"
        )
#endif
    }

    private static func codingPath(_ path: [CodingKey]) -> String {
        guard !path.isEmpty else { return "<root>" }
        return path.map(\.stringValue).joined(separator: ".")
    }

    private func debugLogWAVUpload(
        kind: String,
        wav: Data,
        hasPrimaryTranscript: Bool
    ) {
#if DEBUG
        let headerBytes = min(44, wav.count)
        let pcmBytes = max(0, wav.count - headerBytes)
        let duration = Double(pcmBytes) / 32_000
        print(
            "[MeantByMeGateway] upload kind=\(kind) "
                + "duration=\(String(format: "%.2f", duration))s "
                + "bytes=\(wav.count) "
                + "primary_text_present=\(hasPrimaryTranscript)"
        )
#endif
    }
}

enum JSONValue: Decodable {
    case string(String), number(Double), bool(Bool), object([String: JSONValue]), array([JSONValue]), null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null }
        else if let value = try? container.decode(Bool.self) { self = .bool(value) }
        else if let value = try? container.decode(Double.self) { self = .number(value) }
        else if let value = try? container.decode(String.self) { self = .string(value) }
        else if let value = try? container.decode([String: JSONValue].self) { self = .object(value) }
        else { self = .array(try container.decode([JSONValue].self)) }
    }
}
