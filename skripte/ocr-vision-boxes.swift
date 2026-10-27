#!/usr/bin/env swift
/// macOS Vision OCR MIT Positionen — für das Schwärzen von Namensfeldern.
/// Usage: ocr-vision-boxes.swift <image_path>
/// Output: pro Zeile   x<TAB>y<TAB>w<TAB>h<TAB>text
///         x/y/w/h normalisiert (0..1), Ursprung LINKS OBEN (bereits umgerechnet,
///         Vision liefert links unten — die Umrechnung passiert hier).
///
/// Gegenstück zu ocr-vision-swift.swift (nur Text). Bewusst als eigene Datei,
/// damit das bestehende Werkzeug und sein Aufrufer unverändert bleiben.
///
/// Requirements: macOS 12+, keine weiteren Abhängigkeiten.

import Foundation
import Vision
import AppKit

func ocrBoxes(at path: String) -> [(Double, Double, Double, Double, String)] {
    let url = URL(fileURLWithPath: path)
    guard let image = NSImage(contentsOf: url),
          let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil)
    else { return [] }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["de-DE"]
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try? handler.perform([request])
    guard let results = request.results else { return [] }

    var out: [(Double, Double, Double, Double, String)] = []
    for obs in results {
        guard let top = obs.topCandidates(1).first else { continue }
        let b = obs.boundingBox                       // Ursprung links UNTEN
        let x = Double(b.minX)
        let y = 1.0 - Double(b.maxY)                  // -> Ursprung links OBEN
        out.append((x, y, Double(b.width), Double(b.height), top.string))
    }
    return out
}

let args = CommandLine.arguments
guard args.count >= 2 else {
    fputs("Usage: ocr-vision-boxes.swift <image_path>\n", stderr)
    exit(1)
}
guard FileManager.default.fileExists(atPath: args[1]) else {
    fputs("Error: File not found: \(args[1])\n", stderr)
    exit(1)
}
for (x, y, w, h, text) in ocrBoxes(at: args[1]) {
    let sauber = text.replacingOccurrences(of: "\t", with: " ")
                     .replacingOccurrences(of: "\n", with: " ")
    print(String(format: "%.5f\t%.5f\t%.5f\t%.5f\t%@", x, y, w, h, sauber))
}
