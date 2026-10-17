// Inspect, export a compatible MP4, and sample frames from a real screen recording.
// Usage: swift scripts/video_artifact.swift INPUT.mov OUTPUT.mp4 EVIDENCE_DIRECTORY
import AVFoundation
import AppKit
import Foundation

let args = CommandLine.arguments
if args.count != 4 {
    fatalError("Usage: video_artifact.swift INPUT.mov OUTPUT.mp4 EVIDENCE_DIRECTORY")
}
let sourceURL = URL(fileURLWithPath: args[1])
let outputURL = URL(fileURLWithPath: args[2])
let evidenceURL = URL(fileURLWithPath: args[3], isDirectory: true)
if FileManager.default.fileExists(atPath: outputURL.path) {
    fatalError("Output already exists; refusing to overwrite")
}
try FileManager.default.createDirectory(at: evidenceURL, withIntermediateDirectories: true)
try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
let asset = AVURLAsset(url: sourceURL)
let duration = try await asset.load(.duration)
let tracks = try await asset.loadTracks(withMediaType: .video)
guard let track = tracks.first, duration.seconds.isFinite, duration.seconds > 0 else {
    fatalError("No valid video track")
}
let size = try await track.load(.naturalSize)
guard let exporter = AVAssetExportSession(asset: asset, presetName: AVAssetExportPreset1920x1080) else {
    fatalError("Cannot initialize MP4 exporter")
}
try await exporter.export(to: outputURL, as: .mp4)
let exported = AVURLAsset(url: outputURL)
let exportedDuration = try await exported.load(.duration)
guard abs(exportedDuration.seconds - duration.seconds) < 0.2 else {
    fatalError("Export duration differs from recording")
}
let generator = AVAssetImageGenerator(asset: exported)
generator.appliesPreferredTrackTransform = true
generator.maximumSize = CGSize(width: 1280, height: 720)
var frames: [[String: Any]] = []
for fraction in [0.10, 0.40, 0.65, 0.95] {
    let time = CMTime(seconds: duration.seconds * fraction, preferredTimescale: 600)
    let (image, actual) = try await generator.image(at: time)
    let name = "frame-\(Int(fraction * 100)).png"
    let bitmap = NSBitmapImageRep(cgImage: image)
    try bitmap.representation(using: .png, properties: [:])!.write(to: evidenceURL.appendingPathComponent(name))
    frames.append(["file": name, "seconds": actual.seconds])
}
let metadata: [String: Any] = [
    "source": "actual macOS screencapture recording; no synthetic/reconstructed frames",
    "duration_seconds": duration.seconds,
    "mp4_duration_seconds": exportedDuration.seconds,
    "source_width": size.width,
    "source_height": size.height,
    "mp4_bytes": try FileManager.default.attributesOfItem(atPath: outputURL.path)[.size]!,
    "frames": frames,
    "audio_requested": false,
]
let json = try JSONSerialization.data(withJSONObject: metadata, options: [.prettyPrinted, .sortedKeys])
try json.write(to: evidenceURL.appendingPathComponent("video-metadata.json"))
print(String(data: json, encoding: .utf8)!)
