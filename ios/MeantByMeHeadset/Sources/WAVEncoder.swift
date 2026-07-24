import Foundation

enum WAVEncoder {
    static func pcm16Mono16k(_ pcm: Data) -> Data {
        var output = Data()
        output.appendASCII("RIFF")
        output.appendLE(UInt32(36 + pcm.count))
        output.appendASCII("WAVE")
        output.appendASCII("fmt ")
        output.appendLE(UInt32(16))
        output.appendLE(UInt16(1))
        output.appendLE(UInt16(1))
        output.appendLE(UInt32(16_000))
        output.appendLE(UInt32(32_000))
        output.appendLE(UInt16(2))
        output.appendLE(UInt16(16))
        output.appendASCII("data")
        output.appendLE(UInt32(pcm.count))
        output.append(pcm)
        return output
    }
}

private extension Data {
    mutating func appendASCII(_ value: String) {
        append(value.data(using: .ascii)!)
    }

    mutating func appendLE<T: FixedWidthInteger>(_ value: T) {
        var littleEndian = value.littleEndian
        Swift.withUnsafeBytes(of: &littleEndian) { append(contentsOf: $0) }
    }
}
