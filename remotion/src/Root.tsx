import React from "react";
import { Composition } from "remotion";
import { VideoComposition, TOTAL_FRAMES } from "./compositions/VideoComposition";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="VideoComposition"
    component={VideoComposition}
    durationInFrames={TOTAL_FRAMES}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={{}}
  />
);
