import { PixelPipeline, makeToonGradient } from './render/pixelPipeline';
import { Town } from './world/town';

const canvas = document.getElementById('view') as HTMLCanvasElement;
const pipeline = new PixelPipeline(canvas);
const gradient = makeToonGradient();
const town = new Town(gradient);

pipeline.viewHeight = 2.85;
pipeline.pitchDeg = 30;
pipeline.yawDeg = -14;
pipeline.pixelScale = 2;
pipeline.focus.set(2.32, 0.12, 0.24);

function tick(): void {
  requestAnimationFrame(tick);
  pipeline.render(town.scene);
}
tick();
