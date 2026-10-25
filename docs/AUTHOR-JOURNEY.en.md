[简体中文](AUTHOR-JOURNEY.md) | **English** | [Русский](AUTHOR-JOURNEY.ru.md)

[Back to the homepage](../README.en.md) · [Documentation](README.en.md)

# From beginner to builder: the author's Microduck journey

**A learning timeline and a record of the questions asked along the way**

This project records two learning tracks that both began with the basics: boards, components, circuits, soldering, and assembly on one side; GitHub, running the official software, training, model deployment, and service responsibilities on the other. The author learned through questions and hands-on work, gradually bringing these parts together into a usable system. This page preserves the complete initial recap and adds the robot software learning process.

**Author: kissqy · Compiled: October 13, 2026 · Period covered: August 31–October 13, 2026**

[Learning timeline](#timeline) · [Complete initial reply](#full-recap) · [Robot software supplement](#software-learning) · [Related build records](#related)

<a id="timeline"></a>

## Learning timeline: robot software and hardware developing together

All dates use Beijing time (UTC+8). The software track follows historical questions and related work records, detailed in the [robot software supplement](#software-learning). Hardware milestones come from the existing [HAT build timeline](../hardware/HAT-TIMELINE.en.md) and [IMU build timeline](../hardware/IMU-TIMELINE.en.md). Questions, operations, and build stages are identified according to their respective records.

### The robot software track

| Date | What was happening | How understanding and practical work developed |
| --- | --- | --- |
| **2026-08-31** | Asking whether a “clone” on GitHub changes with the original repository, whether the project can be copied first, and how a downloaded ZIP differs. | Starting with obtaining the code and clarifying the relationship between a project copy, local source files, and upstream changes. |
| **2026-08-31–09-01** | Preparing to run the official software and Fake Robot, checking whether to move the work to a Mac, then progressing to official software deployment and SSH on the ZERO. | Working through development and verification on a computer, alongside installation and operation on the ZERO. |
| **2026-09-02** | Asking whether training the duck's movements requires data, video, or text. | Beginning with the input materials and the form that robot training takes. |
| **2026-09-22** | Asking about an actual physics simulation of the duck, requesting visible training and parameter settings, and asking for the training interface to start independently of the ZERO. | Making training a visible, usable computer workflow and clarifying its role alongside real-robot operation. |
| **2026-09-26–28** | Asking how long training will take, requesting step-by-step guidance, and checking whether training can begin or still needs data and parameters. | Working through the environment, configuration, training steps, and expected results. |
| **2026-10-02** | Asking whether importing a model into the ZERO service requires only ONNX, and what else is needed to use a self-trained model. | Learning the deployment steps between a training export and a model that the robot service can load. |
| **2026-10-02** | Checking whether new training requires a console update, remains compatible with the ZERO service, can reuse an older walking model for joint training, and needs a firmware upgrade. | Connecting individual training tasks, joint training, model files, consoles, and the robot runtime. |
| **2026-10-06** | Asking how Training Studio communicates with WSL. | Following an interface action through to the environment that actually runs the training. |
| **2026-10 (later conversations)** | Asking for clear separation of Linux system functions, the robot service, gamepad input, and model loading; checking how to invoke upstream actions and whether compiled firmware is available. | Progressing from using software to defining responsibilities, integrating features, and checking that a release is usable. |
| **2026-10-13** | Reviewing basic questions and explicitly adding that robot software was also new territory; publishing the complete recap and software learning record on GitHub. | Recording software and hardware as two parts of the same learning process. |

### The electronics and physical build track

| Date | What was happening | How understanding and practical work developed |
| --- | --- | --- |
| **2026-08-31** | Asking where the 15 motors plug in, what the board in the middle is, and whether an IMU is a gyroscope. | Building a basic understanding of the ZERO, HAT, IMU, and servo responsibilities. |
| **2026-09-03** | Discussing the relationship between a schematic and PCB placement, component counts, and the work involved in manual assembly. | Connecting electrical relationships, physical layout, and home assembly conditions. |
| **2026-09-04–07** | Asking about GND, the programming header, mounting-hole dimensions, and the 40-pin connection; progressing the IMU design and the two-layer HAT with placement by function, then moving to fabrication. | Turning component and connector knowledge into buildable schematics, footprints, and board outlines. |
| **2026-09-08–10** | Clarifying power and connector roles, assembling and flashing the IMU, verifying real orientation readings. | Moving from drawings to hardware and verifying communication and actual sensor operation separately. |
| **2026-09-10–14** | Completing HAT assembly, continuing to understand decoupling, battery voltage, and servo power paths, and testing audio and a single servo separately. | Learning while building and checking circuit operation through individual functions. |
| **2026-09-20–23** | Reusing the IMU hardware for Feetech protocol support, testing the shared bus, integrating 15 servos, and learning about assembly, the reference pose, and calibration. | Moving from board-level verification to the whole robot and connecting physical poses with software position values. |
| **2026-10-01** | Asking whether a Feetech servo can assign 2048 to its current position and considering assembly before setting the midpoint. | Thinking further about assembly order and calibration steps. |
| **2026-10-12** | Reviewing the HAT and IMU builds, explaining cost, home assembly, and complexity considerations behind the two-layer choice, and confirming extended use in the robot. | Reviewing the process from component analysis and design choices through layout, construction, and verification. |

**Hardware status, confirmed October 12, 2026: the custom HAT and independent torso IMU have both passed extended use in the complete robot, operate normally, and have no identified issues.** See the two build records above.

<a id="full-recap"></a>

## Complete question recap: the reply from October 13, 2026

The following is a complete English translation of the AI reply to the author's question, “What were the most basic beginner questions I asked about this project, including electronics?” The questions were originally asked in Chinese; “you” refers to the project author. The full explanations, dates, and source notes are retained. The [Chinese edition](AUTHOR-JOURNEY.md#full-recap) preserves the original reply.

<!-- BEGIN TRANSLATED REPLY -->

Yes. I went back through a set of historical records. **Your early questions really did start with things like “What is this board?”, “Where do the motors plug in?”, “What does this component do?”, and “Where does the other end of this pin header connect?” There were especially many of these questions about electronics.**

I take your phrase “the most beginner-level questions” to mean **questions where you first needed to understand what something was, what it did, how to connect it, or how to use it.** Below, I have kept your original questions as closely as possible, adding a little punctuation. Where I found a date for an individual message, I have given it in Beijing time; otherwise, I have identified the conversation it came from.

## 1. Getting to know the duck’s hardware: which boards are there, and what does each one do?

This group captures your starting point particularly well. These questions were concentrated on **August 31**.

| Your original question | What you were trying to understand |
|---|---|
| **“So where do the 15 motors plug in?”** | Whether the motors connect to the main computer or to another board. |
| **“What is this board in the middle? Is it open source? Can you buy it?”** | Identifying the board between the ZERO and the servos. |
| **“So in the end there should be two boards: a Radxa ZERO 3W, and another board that combines the power supply and the motor interface—is that right? I still don’t have a very clear picture.”** | Establishing which parts make up the robot and what each one is responsible for. |
| **“An IMU is a gyroscope, right?”** | Beginning with the sensor’s name and purpose to understand what an IMU is. |

Source: historical project messages, August 31, 2026.

You explicitly said **“I still don’t have a very clear picture”** at the time. That gives a clear indication that you were still building your understanding of the complete hardware system.

## 2. Electronics basics: what are the components, and where does the power come from?

### 1. What exactly does “decoupling” mean?

Your full question was:

> **“I looked at this open-source design. What does its ‘decoupling’ mean? Does ours have it? Please explain decoupling in detail: its function, what it does, why it is needed, and when you should add it.”**

This was your original question from **September 13**, in the records associated with the conversation “Recreating the IMU: DXL Analysis” (《复原IMU DXL分析》).

This is a very typical introductory electronics question, and you covered it thoroughly: **what the term means, what it does, why it is needed, whether your own board has it, and when it should be added.**

### 2. What does an individual component on the board do?

You also asked directly:

> **“What does U4 do?”**

Source: the conversation “Recreating the IMU: DXL Analysis” (《复原IMU DXL分析》).

This is a basic question, and it fits the way you were learning at the time: seeing a component reference on the board and working out its role, one component at a time.

### 3. Does the board have a ground connection?

> **“This board doesn’t seem to have GND?”**

This was your original question from **September 4**, during the discussion of making and laying out the IMU board.

### 4. How are the battery and servos connected for power?

On **September 14**, you asked:

> **“How many volts does the battery in the official design output?”**

You then asked:

> **“So how is the official version wired? Where do its servos get their power?”**

You had also checked the HAT’s role on **September 8**:

> **“Is the HAT what powers the servos in the official design? Does the HAT both power the ZERO 3W and convert battery power for the servos?”**

These are all basic questions that directly shaped your understanding of the whole robot: **where the battery connects, which board handles power, and where the ZERO and servos each get their power.**

Sources: historical messages about the IMU board on September 4; historical messages about HAT power delivery on September 8 and September 14.

## 3. Wiring and flashing firmware: where does it plug in, and what connects to the other end?

This group is also very representative.

| Your original question | Date / source |
|---|---|
| **“What is that 5P pin header for?”** | September 4, messages about the IMU board |
| **“One end of the 5P connection goes to our board. Where does the other end connect? How do we flash the firmware?”** | September 4, messages about the IMU board |
| **“The official board has J11, J3, J13, and J14. What does each one do? Which port does the battery go into, which one powers the IMU board, and does the IMU connect to the servo bus?”** | September 9, HAT / IMU wiring discussion |
| **“Which board does the distance-sensing module connect to?”** | September 10 |
| **“When the time comes, how do we set this board’s ID to 200?”** | The conversation “Recreating the IMU: DXL Analysis” (《复原IMU DXL分析》) |

**“One end of the 5P connection goes to our board. Where does the other end connect?”** is especially concrete. You needed the physical connections to be explained clearly; simply calling something a “programming interface” was not enough.

In the HAT discussion on **September 5**, you also repeatedly checked whether the holes for the 40-pin connector were only for mounting or clearance, whether a pin header needed to be soldered in, and why the ZERO and HAT could not simply make electrical contact through the plated holes. This item is a summary of the historical record; the complete original wording was not retrieved.

## 4. PCB design and soldering: once you have the schematic, what comes next?

### 1. If the schematic already has all the connections, is placing the components all that remains?

On **September 3**, you said:

> **“Can you analyze this board? If we just take the schematic, and the schematic includes all the wiring, then all that’s left is placement…as long as everything fits.”**

This is an excerpt from your original wording. You were working out **the relationship between the electrical connections specified in a schematic and the physical positions of components on a PCB.**

It also provides a clear starting point for your later requests to “explain the components’ functions first, then group and place them by function.”

### 2. How much work is manual component placement?

Also on **September 3**, you asked:

> **“How many components are there on this board in total?”**

> **“Will placing all of those by hand wear me out?”**

These two questions reflect your practical approach to making things: first find out how many parts need to go onto the board, and whether you can realistically do the work yourself.

### 3. Is the capacitor through-hole or surface-mount?

When discussing a **1000 µF / 16 V electrolytic capacitor**, you asked:

> **“Is it the type with leads, or a surface-mount part?”**

Source: the conversation “Writing Code for a JLCEDA Schematic” (《编写嘉立创原理图代码》).

### 4. How large should the pad around a screw hole be?

On **September 4**, you asked:

> **“What should the inner and outer diameters of the pad around an M2 screw hole be, in mils?”**

This is a basic practical question that arises when you first translate physical dimensions into a PCB design: how an M2 screw, the hole diameter, the pad’s outer diameter, and the software’s units relate to one another.

Sources: the PCB-making discussion on September 3, messages about the IMU board layout on September 4, and the conversation “Writing Code for a JLCEDA Schematic” (《编写嘉立创原理图代码》).

## 5. Servos and mechanics: what is calibration, and can you set the midpoint after assembly?

There were several very basic original questions in this area too.

| Your original question | Date / source |
|---|---|
| **“For calibration, does it need to be assembled first?”** | September 22 |
| **“What is the standard pose…?”** | September 22, excerpt from the original wording |
| **“You mean we can change the servo’s current position value to 2048, right?”** | September 23 |
| **“It looks like our console can set that, right? How exactly do we do it?”** | September 23 |
| **“Can a Feetech servo assign 2048 to its current position?”** | October 1 |
| **“Then couldn’t we assemble it first and reset it to 2048 afterward?”** | October 1, a follow-up confirmation to the previous question |
| **“Why does a 3D-printed slope have these steps, and how can we make it smooth?”** | The conversation “How to Smooth Sloped Surfaces in 3D Printing” (《3D打印斜面平滑方法》) |

This group of questions was mainly about understanding **how the physical assembly pose, the servo’s position values, and the calibration procedure fit together.**

## 6. Software, training, and websites: introductory practical questions in these areas too

### 1. How do you connect a new computer to the ZERO without entering a password?

Your original question was:

> **“How do I set up the new computer for passwordless SSH login to the ZERO?”**

Source: the conversation “Analyzing Joint Training Problems” (《联合训练问题分析》).

This is a very concrete introductory Linux / SSH question.

### 2. Can you stop training once the score reaches its highest point?

After looking at the training curve, you asked:

> **“You can see that as training continues, the average still isn’t as high as it was earlier. Does that mean it peaked at 2,000 iterations and there’s no need to continue?”**

Source: the conversation “Increasing Parallelism to Speed Up Training” (《加大并行加快训练》). Punctuation was added to the original question, and the Chinese wording “看的出来” was corrected to “看得出来.”

You were learning how to assess training progress: **whether more training iterations necessarily mean that the model keeps improving.**

### 3. Do you have to buy the domain from the same platform that hosts the website?

When preparing an open-source project and demonstration website for the duck, you asked:

> **“I want to deploy an open-source project and demo website for the duck, and register a domain. Do I have to register the domain through that platform, or can I register it anywhere?”**

Source: the conversation “Cloud Hosting and Domain Registration Advice” (《云服务器域名注册建议》), excerpt from the original wording.

You were clarifying the relationship between domain registration and website hosting.

---

**These original questions show that your starting point in electronics really was learning “what this is, what it does, and where the wires connect.”** Your questions then gradually moved into the relationship between schematics and PCBs, grouping components, power paths, and actually making the boards.

There has also been a very clear pattern in how you ask questions: **after asking about a concept, you follow up with “Does ours have it?”, “Where exactly does it connect?”, and “How do I do it?”** Your questions about decoupling and where the other end of the 5P connection goes illustrate that process particularly well.

<!-- END TRANSLATED REPLY -->

<!-- BEGIN SOFTWARE SUPPLEMENT -->

<a id="software-learning"></a>

## Supplement: learning robot software from the basics too

On October 13, 2026, after reading the review above, the author added:

> **“It feels like you recorded more of my electronics questions, but I’m also very much a beginner when it comes to robot software.”**

Further review made the starting point of your software learning clearer too: how to obtain the code, where to run the official programs, what training requires, how to install a model on the ZERO, and how the training console and robot service work together. The following adds those actual questions. The quotations retain your conversational wording, with punctuation added; entries available only as summaries are identified separately.

### 1. How do you get the code, and will a copy change along with the main repository?

On **August 31, 2026**, you asked:

> **“Will a clone on GitHub change when the main repository changes?”**

You then said:

> **“I want to copy the materials first.”**

> **“Can I just clone a copy?”**

You also specifically clarified:

> **“I mean cloning it on GitHub, not downloading it to my computer.”**

Later that same day, when beginning to use the code locally, you asked:

> **“What I have now is a downloaded ZIP file. Is there any difference?”**

This group records the starting point of your software work: first understanding how a project copy on GitHub, code downloaded to your computer, and later upstream changes relate to one another. Your use of the word “clone” at the time is retained here.

Source: historical project messages, August 31, 2026.

### 2. Where does the official software run, and which computer should you work on next?

As you prepared for the “Official Software and Fake Robot” stage, you had downloaded the official repository and frozen its version. You then asked:

> **“Should I move over to the Mac for the next steps?”**

This is an excerpt from your original question on **August 31, 2026**. You were checking the practical sequence: once you had the code, which environment should you use to install the tools, run the programs, and verify them?

The project records from **September 1** then move on to deploying the official software on the Radxa ZERO 3W, including practical steps such as connecting from your computer to the ZERO over SSH and running the deployment process. This paragraph summarizes the work recorded at the time, showing that learning the software involved both development and verification on a computer and installation and execution on the ZERO.

Sources: messages about “Official Software and Fake Robot” on August 31, 2026; records of deploying the official software on the ZERO on September 1.

### 3. To train the duck, do you provide data, videos, or text?

On **September 2, 2026**, you asked a very direct question:

> **“To train the duck’s movements, do I give it data, videos, or text?”**

This records your initial question about robot training: if you wanted the duck to learn movements, what materials did you need to provide, and how would the training process begin?

Later, in the discussion on **September 22**, you also asked whether there was an actual physics simulation of the duck. You wanted a training mode, a live view of training, and parameter settings, and proposed that the training console should launch independently without relying on the ZERO. This paragraph is a summary of the historical discussion. It records how you began turning the idea of “training” into a computer workflow you could see and operate.

Sources: the original question about training movements on September 2, 2026; discussions of the training console and physics simulation on September 22.

### 4. How long would training take, and what should the first step be?

On **September 26, 2026**, you asked:

> **“If we train it ourselves, how long would it take to get it to that level?”**

You then asked:

> **“Then go ahead. Teach me how to do it, step by step.”**

By **September 28**, you were still checking where training should begin:

> **“Are we supposed to start training now, or what?”**

At the time, you also asked for a review of the whole task to check whether all the data and parameters needed for training were ready. These records show that, before starting, you needed to work through the environment, configuration, operating steps, and expected results. The question in the full review above about whether to stop when training scores no longer improve then records how you learned to assess the training process itself.

Sources: historical training-related messages from September 26 and September 28, 2026.

### 5. Once you have trained a model, how do you actually put it on the duck?

On **October 2, 2026**, you asked:

> **“What do we need to import it into the service on the ZERO? Is the ONNX file alone enough?”**

You also asked that same day:

> **“What do we need to integrate our own models?”**

These two questions directly capture a part of the learning needed to move from training to the physical robot: how the exported files become a model that the robot service on the ZERO can actually load and use. You were checking what else was needed to complete that integration.

Sources: messages about model export and import on October 2, 2026; the conversation “Why Model Import Failed” (《模型导入失败原因》).

### 6. New training, old models, the console, and firmware: which parts need to be updated together?

On **October 2, 2026**, you checked several of these relationships in succession:

| Your original question | The relationship you were trying to understand |
| --- | --- |
| **“If I use the new version for training, do you need to update it in the console for me? The new joint training for walking, falling, and getting up.”** | How the new training workflow is launched and used through the training console. |
| **“Also, will the new training work with the service currently on my ZERO?”** | Whether the training output is compatible with the existing service running on the physical robot. |
| **“I’ve already trained flat-ground walking with the old version. Can the console use that directly for the new joint walking-and-getting-up training?”** | Whether the existing walking model can be used in the subsequent joint training. |
| **“If we use the new joint training, do we need to upgrade the system firmware, or is it mostly a matter of applying a patch?”** | Which layer of the robot’s software actually needs updating when the training approach changes. |

This group connects model training, the training console, the robot service, and firmware deployment. It also shows you beginning to actively check how the parts fit together.

Sources: messages associated with “Increasing Parallelism to Speed Up Training” (《加大并行加快训练》) on October 2, 2026, and the discussion of firmware upgrades for joint training.

The software records trace this progression: **obtain the code → run the official programs → understand training inputs and physics simulation → start training → import models → check service and firmware compatibility.** Together with electronics, soldering, and mechanical assembly, this forms the author’s learning journey through the Microduck project.

<!-- END SOFTWARE SUPPLEMENT -->

<a id="related"></a>

## Related build records

- [HAT build timeline](../hardware/HAT-TIMELINE.en.md): component analysis, the two-layer design, home reflow, and robot integration.
- [IMU build timeline](../hardware/IMU-TIMELINE.en.md): independent hardware and real orientation readings, followed by bus adaptation and robot verification.
- [Hardware projects and notes](../hardware/README.en.md)
- [Back to the project homepage](../README.en.md)
