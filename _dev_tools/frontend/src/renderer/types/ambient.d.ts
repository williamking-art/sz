// 第三方模块类型补充（d3-delaunay 无 @types 包）
declare module "d3-delaunay" {
  export class Delaunay {
    readonly points: Float64Array;
    static from(points: ArrayLike<[number, number]>): Delaunay;
    neighbors(i: number): IterableIterator<number>;
    find(x: number, y: number, i?: number): number;
  }
  export class Voronoi {
    constructor(delaunay: Delaunay, bounds: [number, number, number, number]);
    render(): string;
  }
}
