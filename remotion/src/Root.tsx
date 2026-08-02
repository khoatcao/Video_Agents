import React from "react";
import { Composition } from "remotion";
import { VideoComposition } from "./compositions/VideoComposition";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="VideoComposition"
    component={VideoComposition}
    durationInFrames={420}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={{}}
  />
);
