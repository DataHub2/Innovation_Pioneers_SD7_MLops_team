// Minimal OCR helper: macOS Vision framework, no external dependencies.
//   swift ocr.swift <image> [<image> ...]
import Foundation
import Vision
import AppKit

let paths = Array(CommandLine.arguments.dropFirst())
guard !paths.isEmpty else {
    FileHandle.standardError.write("usage: swift ocr.swift <image>...\n".data(using: .utf8)!)
    exit(2)
}

for path in paths {
    guard let img = NSImage(contentsOfFile: path),
          let tiff = img.tiffRepresentation,
          let bmp = NSBitmapImageRep(data: tiff),
          let cg = bmp.cgImage else {
        print("### FAILED TO LOAD: \(path)")
        continue
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    req.recognitionLanguages = ["en-US", "sv-SE"]

    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do {
        try handler.perform([req])
    } catch {
        print("### OCR ERROR on \(path): \(error)")
        continue
    }
    print("===== \(path) =====")
    if let obs = req.results {
        // Vision returns observations roughly top-to-bottom; sort explicitly
        // by vertical position so the reading order is reliable.
        let sorted = obs.sorted { a, b in
            let ay = a.boundingBox.origin.y, by = b.boundingBox.origin.y
            if abs(ay - by) > 0.012 { return ay > by }
            return a.boundingBox.origin.x < b.boundingBox.origin.x
        }
        for o in sorted {
            if let c = o.topCandidates(1).first {
                print(c.string)
            }
        }
    }
    print("")
}
