// topojson-server 无官方类型声明的轻量补充
declare module "topojson-server" {
  export function topology(objects: {
    [key: string]: GeoJSON.FeatureCollection | GeoJSON.GeometryObject;
  }): TopoJSON.Topology;
}