import Foundation

enum GatewayClientError: LocalizedError {
    case invalidConfiguration
    case invalidResponse
    case server(Int, String)

    var errorDescription: String? {
        switch self {
        case .invalidConfiguration: return "后端地址或访问配置无效"
        case .invalidResponse: return "后端返回了无法识别的数据"
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

    func createSession(language: String = "zh", profileRef: String = "lin_yue_demo") async throws -> DemoResponse {
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
            throw GatewayClientError.invalidResponse
        }
        sessionId = response.session.sessionId
        sessionToken = token
        return response
    }

    func uploadExpression(wav: Data, primaryTranscript: String) async throws {
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
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
    }

    func command(
        _ command: String,
        payload: [String: Any] = [:],
        confirmationMethod: String? = nil
    ) async throws -> DemoResponse {
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

    func interpretCommand(wav: Data, primaryTranscript: String) async throws -> EarbudInterpretation {
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
        addHeaders(to: &request, includeSession: true)
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        do {
            return try JSONDecoder().decode(EarbudInterpretation.self, from: data)
        } catch {
            throw GatewayClientError.invalidResponse
        }
    }

    func audio(kind: String) async throws -> Data {
        let url = baseURL.appendingPathComponent(
            "/api/sessions/\(sessionId)/audio/\(kind)"
        )
        var request = URLRequest(url: url)
        addHeaders(to: &request, includeSession: true)
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        return data
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
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw GatewayClientError.invalidResponse
        }
    }

    private func addHeaders(to request: inout URLRequest, includeSession: Bool) {
        request.setValue(demoToken, forHTTPHeaderField: "X-Demo-Token")
        if includeSession {
            request.setValue(sessionToken, forHTTPHeaderField: "X-Demo-Session")
        }
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            throw GatewayClientError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = (
                try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            )?["detail"] as? String ?? "请求失败"
            throw GatewayClientError.server(http.statusCode, message)
        }
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
