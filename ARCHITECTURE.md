# Architecture

## Physical topology

The AI Thinker ESP32-CAM is both the camera endpoint and actuator controller.
It creates a WPA2 access point named `DroneTracker` on channel 6 with address
`192.168.4.1`. The Mac joins that network and opens one TCP connection to port
5005. No router, second ESP32, browser service, or remote inference server is
part of this branch.

The same socket is bidirectional:

- ESP32-CAM to Mac: framed JPEG images.
- Mac to ESP32-CAM: four-byte servo commands.

## Wire protocols

Each JPEG begins with a six-byte little-endian header:

```text
offset  size  value
0       2     0xFF 0xAA
2       4     JPEG payload length, uint32 little-endian
6       N     JPEG bytes
```

The Mac rejects zero-length frames and frames larger than 200,000 bytes. Its
incremental parser searches for the marker after corruption and retains a
trailing `0xFF` when the marker is divided across two TCP reads. A receiver
thread publishes complete JPEGs into a queue of length one, evicting the older
frame whenever the application is still processing.

Each servo command is four bytes:

```text
offset  size  value
0       2     0xBB 0xCC
2       1     pan angle, uint8, clamped to 0-180
3       1     tilt angle, uint8, clamped to 0-180
```

The firmware consumes the byte stream with a four-state marker parser so a
partial command is retained across loop iterations.

## Frame lifecycle

1. The OV2640 captures QVGA JPEG at a target rate of 10 fps. With PSRAM, the
   firmware uses two frame buffers and `CAMERA_GRAB_LATEST`; without PSRAM, it
   falls back to one DRAM buffer and `CAMERA_GRAB_WHEN_EMPTY`.
2. The Mac receiver decodes the newest complete JPEG with OpenCV and rotates it
   180 degrees for the physical camera orientation.
3. Every tenth processed frame, or whenever tracking is lost, Grounding DINO
   runs synchronously on that frame and returns the highest-confidence box for
   the configured text prompt.
4. The new box becomes a mask for `cv2.goodFeaturesToTrack`: at most 20 corners,
   quality level 0.20, minimum spacing 7 pixels, and block size 7.
5. On intervening frames, `cv2.calcOpticalFlowPyrLK` propagates the points with
   a 7 x 7 search window, two pyramid levels, and a 10-iteration/0.03-epsilon
   termination criterion.
6. The median surviving point displacement translates the entire bounding box.
   Fewer than three surviving points clears the track and requests immediate
   Grounding DINO inference.
7. An EMA with `alpha=0.40` filters horizontal and vertical box-center error.
   Outside a 10-pixel dead zone, normalized error maps to servo angles and the
   four-byte command returns over the camera socket.

Inference blocks the main processing loop, but it does not block the receiver
thread. Frames arriving during inference replace one another in the one-slot
queue, so processing resumes from the newest received image instead of working
through an obsolete backlog.

## macOS inference path

The branch pins `IDEA-Research/grounding-dino-tiny` to model revision
`a2bb814dd30d776dcf7e30523b00659f4f141c71`. Hugging Face Transformers provides
the processor and `AutoModelForZeroShotObjectDetection`; PyTorch runs the model
under `torch.inference_mode()`.

Device selection is `mps` when `torch.backends.mps.is_available()` and `cpu`
otherwise. `PYTORCH_ENABLE_MPS_FALLBACK=1` allows an unsupported MPS operation
to execute on CPU. Input resizing is bounded to a 480-pixel short edge and a
640-pixel long edge rather than the processor's larger general-purpose default.
The first model download occurs while the Mac still has Internet access; the
runtime uses `--offline` after the Mac joins the ESP32 access point.

## Limits

- The video is evidence of the physical prototype, not a controlled latency or
  accuracy benchmark.
- KLT assumes short-term appearance consistency and mostly translational box
  motion. Occlusion, scale change, blur, or weak corner texture can cause drift.
- Servo mapping is proportional image alignment, not a dynamic plant model.
- The ESP32 access point isolates the Mac from its normal Wi-Fi network while
  connected unless the Mac has another network interface.
