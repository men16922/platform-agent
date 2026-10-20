// Render original vector text captions only; screenshots remain unchanged.
// Run from this directory: swift render_captions.swift
import AppKit
import Foundation

let data = try Data(contentsOf: URL(fileURLWithPath: "storyboard.json"))
let story = try JSONSerialization.jsonObject(with: data) as! [String: Any]
let scenes = story["scenes"] as! [[String: Any]]
for (index, scene) in scenes.enumerated() {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1920, pixelsHigh: 180,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
    NSColor(calibratedRed: 0.04, green: 0.07, blue: 0.11, alpha: 1).setFill()
    NSRect(x: 0, y: 0, width: 1920, height: 180).fill()
    let lines: [(String, CGFloat, CGFloat, NSColor)] = [
        (scene["title"] as! String, 123, 36, .white),
        (scene["subtitle"] as! String, 69, 28, NSColor(calibratedWhite: 0.88, alpha: 1)),
        ("로컬 kind · 실제 정지화면 편집 · 영상 재생 시간은 작업 소요 시간이 아닙니다", 22, 23,
         NSColor(calibratedWhite: 0.67, alpha: 1)),
    ]
    for (text, y, size, color) in lines {
        (text as NSString).draw(in: NSRect(x: 30, y: y, width: 1860, height: 42),
            withAttributes: [.font: NSFont.systemFont(ofSize: size), .foregroundColor: color])
    }
    NSGraphicsContext.restoreGraphicsState()
    try bitmap.representation(using: .png, properties: [:])!.write(
        to: URL(fileURLWithPath: String(format: "caption-%02d.png", index)))
}
