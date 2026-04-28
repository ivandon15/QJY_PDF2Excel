import Vision
import AppKit
import Foundation

// ocr_extract: 批量OCR，对每张图输出所有文本片段（含归一化坐标）
// 用法: ocr_extract <image_path1> [image_path2 ...]
// 输出: 每张图一行JSON: {"path": "...", "texts": [{"text": "...", "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.05}, ...]}

let args = CommandLine.arguments
guard args.count > 1 else {
    fputs("Usage: ocr_extract <image_path1> [image_path2 ...]\n", stderr)
    exit(1)
}

let imagePaths = Array(args[1...])

for imagePath in imagePaths {
    guard let image = NSImage(contentsOfFile: imagePath),
          let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        let errObj: [String: Any] = ["path": imagePath, "error": "cannot_load", "texts": []]
        if let data = try? JSONSerialization.data(withJSONObject: errObj),
           let line = String(data: data, encoding: .utf8) {
            print(line)
        }
        continue
    }

    var textItems: [[String: Any]] = []
    let semaphore = DispatchSemaphore(value: 0)

    let request = VNRecognizeTextRequest { req, _ in
        defer { semaphore.signal() }
        guard let observations = req.results as? [VNRecognizedTextObservation] else { return }
        for obs in observations {
            guard let top = obs.topCandidates(1).first else { continue }
            // Vision坐标系：原点在左下角，需翻转Y轴
            let b = obs.boundingBox
            let item: [String: Any] = [
                "text": top.string,
                "x": Double(b.origin.x),
                "y": Double(1.0 - b.origin.y - b.size.height),  // 翻转为左上角原点
                "w": Double(b.size.width),
                "h": Double(b.size.height),
                "conf": Double(top.confidence)
            ]
            textItems.append(item)
        }
    }
    request.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"]
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try? handler.perform([request])
    semaphore.wait()

    let output: [String: Any] = ["path": imagePath, "texts": textItems]
    if let data = try? JSONSerialization.data(withJSONObject: output),
       let line = String(data: data, encoding: .utf8) {
        print(line)
    }
}
