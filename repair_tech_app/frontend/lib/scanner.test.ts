import {describe, expect, it, vi} from "vitest";
import {cleanCode, wedgeReader} from "./scanner";

describe("wedgeReader", () => {
  it("reads a fast burst ending in Enter", () => {
    const onScan = vi.fn();
    const feed = wedgeReader(onScan);
    [..."RO/00123"].forEach((key, i) => feed(key, 1000 + i * 10));
    expect(feed("Enter", 1090)).toBe(true);
    expect(onScan).toHaveBeenCalledWith("RO/00123");
  });

  it("ignores a person typing", () => {
    const onScan = vi.fn();
    const feed = wedgeReader(onScan);
    [..."ABCD"].forEach((key, i) => feed(key, 1000 + i * 200));
    expect(feed("Enter", 1900)).toBe(false);
    expect(onScan).not.toHaveBeenCalled();
  });

  it("ignores too short a burst", () => {
    const onScan = vi.fn();
    const feed = wedgeReader(onScan);
    feed("A", 0);
    feed("B", 5);
    feed("Enter", 10);
    expect(onScan).not.toHaveBeenCalled();
  });
});

describe("cleanCode", () => {
  it("drops scanner whitespace", () => {
    expect(cleanCode(" 1FTFW1ET5DFC10312\r\n")).toBe("1FTFW1ET5DFC10312");
  });
});
