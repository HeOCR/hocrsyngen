"""Train a small paper DDPM and apply its textures outside a protected ink mask."""
import base64
import hashlib
import json
from time import monotonic

import numpy as np
from PIL import Image

SEED = 20261121
SIDE = 64
OVERLAP = 16
STRIDE = SIDE - OVERLAP
PAPER = 243


def read_gray(path):
    with Image.open(path) as image:
        return np.asarray(image.convert('L'))


def write_gray(path, pixels):
    Image.fromarray(pixels).save(path)


def blend_paper(tiles, shape, line_id):
    """Overlap 64 px patches with a fixed integer ramp and seeded tile draws."""
    h, w = shape
    ah, aw = (max(SIDE, STRIDE * ((n - 1) // STRIDE) + SIDE) for n in shape)
    blend = np.zeros((ah, aw), dtype=np.int32)
    normalizer = np.zeros_like(blend)
    ramp = np.full(SIDE, OVERLAP + 1, dtype=np.int32)
    ramp[:OVERLAP] = np.arange(1, OVERLAP + 1)
    ramp[-OVERLAP:] = ramp[:OVERLAP][::-1]
    weights = ramp[:, None] * ramp[None, :]
    draw = hashlib.sha256(f'{SEED}:{line_id}'.encode()).digest()
    rng = np.random.default_rng(int.from_bytes(draw[:8], 'big'))
    for i, y in enumerate(range(0, ah - SIDE + 1, STRIDE)):
        for j, x in enumerate(range(0, aw - SIDE + 1, STRIDE)):
            tile = tiles[rng.integers(len(tiles))]
            tile = tile[::(-1 if i % 2 else 1), ::(-1 if j % 2 else 1)]
            window = np.s_[y:y + SIDE, x:x + SIDE]
            blend[window] += tile * weights
            normalizer[window] += weights
    pixels = ((blend + normalizer // 2) // normalizer)[:h, :w]
    return pixels.astype(np.uint8)


def pair(render, tiles, line_id):
    if render.ndim != 2 or render.dtype != np.uint8:
        raise ValueError('Expected an 8-bit grayscale render')
    if not len(tiles) or tiles.shape[1:] != (SIDE, SIDE):
        raise ValueError('Expected a nonempty bank of 64×64 paper tiles')
    protected = render != 255
    if not protected.any() or protected.all():
        raise ValueError('Render must contain protected ink and blank paper')
    control = np.where(protected, render, PAPER).astype(np.uint8)
    treatment = np.where(protected, render, blend_paper(tiles, render.shape, line_id))
    if not np.array_equal(control[protected], treatment[protected]):
        raise ValueError('Paper transform changed a protected pixel')
    if np.array_equal(control, treatment):
        raise ValueError('Paper transform did not change any background pixels')
    return control, treatment, hashlib.sha256(protected.tobytes()).hexdigest()


def fit(crops, weights_path, *, device='cuda', steps=30_000, cutoff=14_400,
        batch_size=32, sample_steps=50, tile_count=128):
    import torch
    from diffusers import DDIMScheduler, DDPMScheduler, UNet2DModel
    from safetensors.torch import save_file

    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('The scheduled paper fit requires CUDA')
    rng = torch.Generator(device=device).manual_seed(SEED)
    images = torch.from_numpy(crops).to(device=device, dtype=torch.float32)[:, None] / 127.5 - 1
    model = UNet2DModel(
        sample_size=SIDE, in_channels=1, out_channels=1, layers_per_block=1,
        block_out_channels=(32, 64, 128), norm_num_groups=8,
        down_block_types=('DownBlock2D',) * 3, up_block_types=('UpBlock2D',) * 3,
    ).to(device)
    scheduler = DDPMScheduler(num_train_timesteps=1000, prediction_type='epsilon')
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0002)
    start = monotonic()
    completed = 0
    model.train()
    for _ in range(steps):
        if monotonic() - start >= cutoff:
            break
        batch = images[torch.randint(len(images), (batch_size,), device=device, generator=rng)]
        timestep = torch.randint(1000, (batch_size,), device=device, generator=rng)
        noise = torch.randn(batch.shape, device=device, generator=rng)
        predicted = model(scheduler.add_noise(batch, noise, timestep), timestep).sample
        loss = torch.nn.functional.mse_loss(predicted, noise)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        completed += 1
    if not completed:
        raise RuntimeError('Paper fit did not complete a step')
    save_file({k: v.detach().cpu().contiguous() for k, v in model.state_dict().items()}, weights_path)
    model.eval()
    ddim = DDIMScheduler.from_config(scheduler.config)
    ddim.set_timesteps(sample_steps, device=device)
    tiles = []
    with torch.inference_mode():
        for start_tile in range(0, tile_count, 16):
            size = min(16, tile_count - start_tile)
            sample = torch.randn((size, 1, SIDE, SIDE), device=device, generator=rng)
            for step in ddim.timesteps:
                sample = ddim.step(model(sample, step).sample, step, sample).prev_sample
            tiles.append(sample[:, 0].cpu().numpy())
    pixels = np.concatenate(tiles) * 127.5
    pixels = np.clip(np.rint(pixels - np.median(pixels) + PAPER), PAPER - 12, PAPER + 12).astype(np.uint8)
    return pixels, completed, dict(model.config)


def write_tiles(path, tiles):
    with path.open('w') as out:
        for tile in tiles:
            raw = tile.tobytes()
            out.write(json.dumps({'sha256': hashlib.sha256(raw).hexdigest(),
                                  'gray64_base64': base64.b64encode(raw).decode()}) + '\n')


def read_tiles(path):
    tiles = []
    for line in path.read_text().splitlines():
        record = json.loads(line)
        raw = base64.b64decode(record['gray64_base64'], validate=True)
        if hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise ValueError('Paper tile hash mismatch')
        tiles.append(np.frombuffer(raw, dtype=np.uint8).reshape(SIDE, SIDE))
    return np.stack(tiles)
