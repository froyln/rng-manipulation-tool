mod focus;
mod worker;
use iced::{
    animation::Animation,
    widget::{
        self, button, checkbox, column, container, mouse_area, pick_list, row, scrollable, text,
        text_input, Space,
    },
    Color, Element, Fill, Length, Subscription, Task, Theme,
};
use serde_json::{json, Value};
use std::{
    collections::BTreeMap,
    path::PathBuf,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use worker::{Coordinate, Event, Worker};

const MODES: [&str; 4] = ["Mob", "Fortune", "Iron", "Gold"];
const BG: Color = Color::from_rgb(0.082, 0.063, 0.125);
const SURFACE: Color = Color::from_rgb(0.129, 0.094, 0.184);
const INK: Color = Color::from_rgb(0.945, 0.918, 0.984);
const MUTED: Color = Color::from_rgb(0.745, 0.690, 0.816);
const PURPLE: Color = Color::from_rgb(0.447, 0.271, 0.675);
const FOCUS: Color = Color::from_rgb(0.812, 0.671, 1.0);
const CAUTION: Color = Color::from_rgb(0.941, 0.741, 0.463);
fn blend(a: Color, b: Color, t: f32) -> Color {
    Color::from_rgba(
        a.r + (b.r - a.r) * t,
        a.g + (b.g - a.g) * t,
        a.b + (b.b - a.b) * t,
        a.a + (b.a - a.a) * t,
    )
}
fn anim(value: f32, ms: u64) -> Animation<f32> {
    Animation::new(value)
        .easing(iced::animation::Easing::EaseOutCubic)
        .duration(Duration::from_millis(ms))
}
fn sample(a: &Animation<f32>) -> f32 {
    a.interpolate_with(|v| v, Instant::now())
}

#[derive(Debug, Clone)]
enum Message {
    Mode(usize),
    Input(&'static str, String),
    Advanced,
    Trace(bool),
    Reduced(bool),
    Plan,
    Search(bool),
    Cancel,
    Tick,
    Hover(usize, bool),
    Copy(String),
    Browse(bool),
    Folder(bool, Option<PathBuf>),
    Keyboard(iced::keyboard::Event),
    Scale(f64),
}
struct Candidate {
    plan: String,
    coordinates: Vec<Coordinate>,
    requirements: Vec<String>,
    region: Vec<String>,
    index: usize,
    directory: PathBuf,
}
struct Draft {
    values: BTreeMap<String, String>,
    trace: bool,
    advanced: bool,
    plan_open: bool,
    result: Option<Candidate>,
    dirty: bool,
}
impl Draft {
    fn new(mode: usize) -> Self {
        let mut values = BTreeMap::new();
        for (k, v) in [
            ("radius", if mode == 2 { "128" } else { "25" }),
            ("mob", "witch"),
            ("bound", "64"),
            ("players_min", "1"),
            ("players_max", "1"),
            ("ore", "diamond"),
            ("level", "3"),
            ("target", "4"),
            ("advances", "0"),
            ("difficulty", "3"),
            ("successes", "1/3"),
            ("world", ""),
        ] {
            values.insert(k.into(), v.into());
        }
        Self {
            values,
            trace: false,
            advanced: false,
            plan_open: false,
            result: None,
            dirty: false,
        }
    }
}
struct App {
    shared: BTreeMap<String, String>,
    drafts: [Draft; 4],
    mode: usize,
    worker: Option<Worker>,
    stage: String,
    error: Option<String>,
    error_field: Option<String>,
    diagnostics: String,
    pending: PathBuf,
    session: PathBuf,
    serial: usize,
    terminal: bool,
    started: Instant,
    cancelling: Option<Instant>,
    dialog: bool,
    reduced: bool,
    scale: f64,
    hover: [Animation<f32>; 14],
    tabs: [Animation<f32>; 4],
    reveal: Animation<f32>,
    result_reveal: Animation<f32>,
}
impl Drop for App {
    fn drop(&mut self) {
        self.worker.take();
        let _ = std::fs::remove_dir_all(&self.session);
    }
}
impl App {
    fn new() -> Self {
        let session = std::env::temp_dir().join(format!(
            "rng-desktop-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir(&session).expect("Could not create desktop temporary directory");
        Self {
            shared: [("seed", ""), ("view", "10"), ("x", "0"), ("z", "0")]
                .map(|(k, v)| (k.into(), v.into()))
                .into(),
            drafts: std::array::from_fn(Draft::new),
            mode: 0,
            worker: None,
            stage: "Enter a world creation seed to begin.".into(),
            error: None,
            error_field: None,
            diagnostics: String::new(),
            pending: PathBuf::new(),
            session,
            serial: 0,
            terminal: false,
            started: Instant::now(),
            cancelling: None,
            dialog: false,
            reduced: std::env::var_os("RNG_REDUCED_MOTION").is_some(),
            scale: 1.0,
            hover: std::array::from_fn(|_| anim(0.0, 120)),
            tabs: std::array::from_fn(|i| anim(if i == 0 { 1.0 } else { 0.0 }, 160)),
            reveal: anim(0.0, 180),
            result_reveal: anim(1.0, 180),
        }
    }
    fn busy(&self) -> bool {
        self.worker.is_some() || self.dialog
    }
    fn tween(&self, target: f32, ms: u64) -> Animation<f32> {
        anim(target, if self.reduced { 0 } else { ms })
    }
    fn start(&mut self, request: Value) {
        self.error = None;
        self.error_field = None;
        self.diagnostics.clear();
        self.terminal = false;
        self.started = Instant::now();
        self.cancelling = None;
        match Worker::start(&worker::tool_dir(), request) {
            Ok(worker) => self.worker = Some(worker),
            Err(e) => self.error = Some(e),
        }
    }
    fn request(&self, next: bool) -> Value {
        let d = &self.drafts[self.mode];
        let mut v: serde_json::Map<String, Value> = self
            .shared
            .iter()
            .chain(d.values.iter())
            .map(|(k, v)| (k.clone(), json!(v)))
            .collect();
        v.insert("exact".into(), json!(d.trace));
        v.insert("skip".into(), json!("0"));
        if next {
            if let Some(c) = &d.result {
                v.insert("skip".into(), json!((c.index + 1).to_string()));
                if c.region.len() == 2 {
                    v.insert("exclude_region".into(), json!(c.region));
                }
            }
        }
        json!({"action":"search","mode":MODES[self.mode],"values":v,"output":self.pending})
    }
    fn update(&mut self, message: Message) -> Task<Message> {
        let mut focus_field = None;
        match message {
            Message::Mode(i) if !self.busy() => {
                self.mode = i;
                let now = Instant::now();
                for j in 0..4 {
                    let target = if i == j { 1.0 } else { 0.0 };
                    if self.reduced {
                        self.tabs[j] = anim(target, 0)
                    } else {
                        self.tabs[j].go_mut(target, now);
                    }
                }
                self.reveal = self.tween(if self.drafts[i].advanced { 1.0 } else { 0.0 }, 180);
                self.error = None;
                self.stage = if self.drafts[i].dirty {
                    "Settings changed. Find a new candidate to export."
                } else if self.drafts[i].result.is_some() {
                    "Modeled candidate ready. Review the build requirements."
                } else {
                    "Enter settings, then find a candidate."
                }
                .into();
                return widget::operation::focus(format!("tab-{i}"));
            }
            Message::Input(key, value) if !self.busy() => {
                if self.shared.contains_key(key) {
                    self.shared.insert(key.into(), value);
                    for d in &mut self.drafts {
                        d.dirty = true;
                    }
                } else {
                    self.drafts[self.mode].values.insert(key.into(), value);
                    self.drafts[self.mode].dirty = true;
                }
                self.stage = "Settings changed. Find a new candidate to export.".into();
                self.error = None;
            }
            Message::Advanced => {
                let d = &mut self.drafts[self.mode];
                d.advanced = !d.advanced;
                let target = if d.advanced { 1.0 } else { 0.0 };
                if self.reduced {
                    self.reveal = anim(target, 0)
                } else {
                    self.reveal.go_mut(target, Instant::now());
                }
            }
            Message::Trace(value) if !self.busy() => {
                self.drafts[self.mode].trace = value;
                self.drafts[self.mode].dirty = true;
            }
            Message::Reduced(value) => {
                self.reduced = value;
                if value {
                    for a in &mut self.hover {
                        *a = anim(a.value(), 0)
                    }
                    for a in &mut self.tabs {
                        *a = anim(a.value(), 0)
                    }
                    self.reveal = anim(self.reveal.value(), 0);
                    self.result_reveal = anim(1.0, 0);
                }
            }
            Message::Plan => self.drafts[self.mode].plan_open = !self.drafts[self.mode].plan_open,
            Message::Hover(i, value) => {
                let target = if value { 1.0 } else { 0.0 };
                if self.reduced {
                    self.hover[i] = anim(target, 0)
                } else {
                    self.hover[i].go_mut(target, Instant::now());
                }
            }
            Message::Search(next) if !self.busy() => {
                if self.shared["seed"].trim().is_empty() {
                    self.error = Some("Enter a world creation seed.".into());
                    return widget::operation::focus("seed");
                }
                self.serial += 1;
                self.pending = self.session.join(format!("candidate-{}", self.serial));
                self.stage = "Calculating candidate…".into();
                self.start(self.request(next));
            }
            Message::Cancel => {
                if let Some(w) = &mut self.worker {
                    if self.cancelling.is_none() {
                        w.cancel();
                        self.cancelling = Some(Instant::now());
                        self.stage = "Cancelling…".into();
                    }
                }
            }
            Message::Tick => {
                let mut events = Vec::new();
                let mut disconnected = false;
                if let Some(w) = &mut self.worker {
                    loop {
                        match w.events.try_recv() {
                            Ok(e) => events.push(e),
                            Err(std::sync::mpsc::TryRecvError::Disconnected) => {
                                disconnected = true;
                                break;
                            }
                            Err(_) => break,
                        }
                    }
                }
                for event in events {
                    match event {
                        Err(details) => self.diagnostics = details,
                        Ok(_) if self.cancelling.is_some() => {}
                        Ok(Event::Progress { stage }) => self.stage = stage,
                        Ok(Event::Result {
                            plan,
                            coordinates,
                            region,
                            index,
                            requirements,
                        }) => {
                            self.drafts[self.mode].result = Some(Candidate {
                                plan,
                                coordinates,
                                region,
                                index,
                                requirements,
                                directory: self.pending.clone(),
                            });
                            self.drafts[self.mode].dirty = false;
                            self.stage =
                                "Modeled candidate ready. Review the build requirements.".into();
                            self.terminal = true;
                            self.result_reveal = anim(if self.reduced { 1.0 } else { 0.0 }, 180);
                            self.result_reveal.go_mut(1.0, Instant::now());
                        }
                        Ok(Event::World { path, seed }) => {
                            self.drafts[3].values.insert("world".into(), path);
                            self.shared.insert("seed".into(), seed);
                            for d in &mut self.drafts {
                                d.dirty = true;
                            }
                            self.stage = "Seed loaded from saved world. No world is edited.".into();
                            self.terminal = true;
                        }
                        Ok(Event::Exported { paths }) => {
                            self.stage =
                                format!("Saved schematic and plan: {}", paths.join("  •  "));
                            self.terminal = true;
                        }
                        Ok(Event::Error { message, field }) => {
                            focus_field = field.clone();
                            self.error_field = field;
                            self.error = Some(message);
                            self.stage =
                                "Action failed. Your settings and previous candidate are retained."
                                    .into();
                            self.terminal = true;
                        }
                        Ok(Event::Cancelled) => {
                            self.terminal = true;
                        }
                    }
                }
                let timed_out = self
                    .cancelling
                    .is_some_and(|t| t.elapsed() > Duration::from_secs(2));
                let finished = if let Some(w) = &mut self.worker {
                    disconnected && w.finished()
                } else {
                    false
                };
                if timed_out && !finished {
                    if let Some(worker) = &mut self.worker {
                        worker.force_stop();
                    }
                }
                if finished {
                    self.worker.take();
                    if self.cancelling.take().is_some() {
                        self.stage =
                            "Search cancelled. You can change settings or try again.".into();
                    } else if !self.terminal {
                        self.error = Some(format!(
                            "Worker stopped before completing. {}",
                            self.diagnostics
                        ));
                    }
                }
            }
            Message::Copy(value) => return iced::clipboard::write(value),
            Message::Browse(export) if !self.busy() => {
                if export
                    && (self.drafts[self.mode].result.is_none() || self.drafts[self.mode].dirty)
                {
                    return Task::none();
                }
                self.dialog = true;
                return Task::perform(
                    async move {
                        rfd::AsyncFileDialog::new()
                            .set_title(if export {
                                "Export schematic and plan"
                            } else {
                                "Select saved Overworld (read-only)"
                            })
                            .pick_folder()
                            .await
                            .map(|f| f.path().to_path_buf())
                    },
                    move |p| Message::Folder(export, p),
                );
            }
            Message::Folder(export, path) => {
                self.dialog = false;
                if let Some(path) = path {
                    if export {
                        if let Some(c) = &self.drafts[self.mode].result {
                            let request =
                                json!({"action":"export","source":c.directory,"destination":path});
                            self.stage = "Saving schematic and plan…".into();
                            self.start(request);
                        }
                    } else {
                        self.stage = "Checking saved world…".into();
                        self.start(json!({"action":"world","path":path}));
                    }
                }
            }
            Message::Scale(scale) => self.scale = scale,
            Message::Keyboard(iced::keyboard::Event::KeyPressed { key, modifiers, .. }) => {
                use iced::keyboard::{key::Named, Key};
                if key == Key::Named(Named::Escape) {
                    return self.update(Message::Cancel);
                }
                if key == Key::Named(Named::Tab) {
                    return if modifiers.shift() {
                        widget::operation::focus_previous()
                    } else {
                        widget::operation::focus_next()
                    };
                }
                if modifiers.control() && key == Key::Named(Named::Enter) {
                    return self.update(Message::Search(false));
                }
                if modifiers.control() && key.as_ref() == Key::Character("s") {
                    return self.update(Message::Browse(true));
                }
            }
            _ => {}
        }
        if let Some(field) = focus_field {
            return widget::operation::focus(field);
        }
        Task::none()
    }
    fn subscription(&self) -> Subscription<Message> {
        let active = self.worker.is_some()
            || self
                .hover
                .iter()
                .chain(self.tabs.iter())
                .chain([&self.reveal, &self.result_reveal])
                .any(|a| a.is_animating(Instant::now()));
        let ticks = if active {
            iced::time::every(Duration::from_millis(16)).map(|_| Message::Tick)
        } else {
            Subscription::none()
        };
        Subscription::batch([ticks, iced::keyboard::listen().map(Message::Keyboard)])
    }
    fn field<'a>(&'a self, key: &'static str, label: &'a str) -> Element<'a, Message> {
        let value = self
            .shared
            .get(key)
            .unwrap_or_else(|| &self.drafts[self.mode].values[key]);
        let mut input = text_input("", value).id(key).padding(10).size(14);
        if !self.busy() {
            input = input.on_input(move |v| Message::Input(key, v));
        }
        let mut field = column![text(label).size(13), input].spacing(7);
        if self.error_field.as_deref() == Some(key) {
            if let Some(error) = &self.error {
                field = field.push(text(error).size(12).color(CAUTION));
            }
        }
        field.into()
    }
    fn choice<'a>(
        &'a self,
        key: &'static str,
        label: &'a str,
        options: &'static [&'static str],
    ) -> Element<'a, Message> {
        let value = self.drafts[self.mode].values[key].as_str();
        let picker = pick_list(options, Some(value), move |v| Message::Input(key, v.into()))
            .padding(10)
            .width(Fill);
        // Freeze choices while a request owns the input snapshot.
        let control: Element<_> = if self.busy() {
            text(value).into()
        } else {
            let index = options.iter().position(|v| *v == value).unwrap_or(0);
            let keys = vec![
                (
                    iced::keyboard::Key::Named(iced::keyboard::key::Named::ArrowRight),
                    Message::Input(key, options[(index + 1) % options.len()].into()),
                ),
                (
                    iced::keyboard::Key::Named(iced::keyboard::key::Named::ArrowLeft),
                    Message::Input(
                        key,
                        options[(index + options.len() - 1) % options.len()].into(),
                    ),
                ),
            ];
            focus::wrap(picker, key, keys)
        };
        column![text(label).size(13), control].spacing(7).into()
    }
    fn action<'a>(
        &'a self,
        id: usize,
        label: impl Into<String>,
        message: Message,
        enabled: bool,
        primary: bool,
    ) -> Element<'a, Message> {
        let t = sample(&self.hover[id]);
        let b = button(text(label.into()).size(14))
            .padding([11, 16])
            .on_press_maybe(enabled.then_some(message.clone()))
            .style(move |_, status| {
                let mut s = button::Style::default();
                let base = if primary { PURPLE } else { SURFACE };
                let hover = blend(base, FOCUS, 0.18);
                s.background = Some(blend(base, hover, t).into());
                s.text_color = if enabled { INK } else { MUTED };
                s.border = iced::Border {
                    color: if status == button::Status::Hovered {
                        FOCUS
                    } else {
                        blend(SURFACE, FOCUS, 0.25)
                    },
                    width: 1.0,
                    radius: 4.0.into(),
                };
                if status == button::Status::Pressed {
                    s.background = Some(blend(base, BG, 0.25).into());
                }
                s
            });
        focus::wrap(
            mouse_area(b)
                .on_enter(Message::Hover(id, true))
                .on_exit(Message::Hover(id, false)),
            format!("action-{id}"),
            if enabled {
                focus::activate(message)
            } else {
                vec![]
            },
        )
    }
    fn settings(&self) -> Element<'_, Message> {
        let d = &self.drafts[self.mode];
        let mut form = column![
            text(MODES[self.mode]).size(26),
            text("Find a build location from modeled RNG.")
                .color(MUTED)
                .size(13)
        ]
        .spacing(16);
        match self.mode {
            0 => {
                form = form
                    .push(self.choice(
                        "mob",
                        "Species",
                        &[
                            "witch", "creeper", "skeleton", "zombie", "spider", "enderman",
                        ],
                    ))
                    .push(
                        row![
                            self.field("players_min", "Minimum players"),
                            self.field("players_max", "Maximum players")
                        ]
                        .spacing(12),
                    )
            }
            1 => {
                form = form
                    .push(self.choice(
                        "ore",
                        "Ore",
                        &["diamond", "coal", "emerald", "quartz", "lapis", "redstone"],
                    ))
                    .push(
                        row![
                            self.field("level", "Fortune level (0–3)"),
                            self.field("target", "Minimum items per ore")
                        ]
                        .spacing(12),
                    )
            }
            2 => {
                form = form
                    .push(text("Build needs 24 doors and 300 adult villagers.").size(14))
                    .push(
                        text("A linked Nether receiver is required; collection is not included.")
                            .color(CAUTION)
                            .size(13),
                    )
            }
            _ => {
                form = form
                    .push(self.choice(
                        "difficulty",
                        "Difficulty (1 easy / 2 normal / 3 hard)",
                        &["1", "2", "3"],
                    ))
                    .push(self.choice(
                        "successes",
                        "Minimum passing checks",
                        &["1/3", "2/3", "3/3"],
                    ))
                    .push(
                        text("2/3 and 3/3 are rarer; no guaranteed rate increase.")
                            .size(12)
                            .color(MUTED),
                    )
                    .push(self.field("world", "Saved Overworld (optional, read-only)"))
                    .push(self.action(
                        7,
                        "Choose saved world…",
                        Message::Browse(false),
                        !self.busy(),
                        false,
                    ))
            }
        }
        form = form.push(self.action(
            4,
            if d.advanced {
                "▾ Advanced"
            } else {
                "▸ Advanced"
            },
            Message::Advanced,
            true,
            false,
        ));
        let amount = sample(&self.reveal);
        if amount > 0.001 {
            let mut advanced =
                column![self.field("radius", "Search radius (80-chunk regions)")].spacing(12);
            if self.mode == 0 {
                advanced =
                    advanced.push(self.field("bound", "Minimum random Y bound (16–256, step 16)"));
            }
            if self.mode == 1 {
                advanced = advanced.push(self.field("advances", "Maximum RNG advances (0–1000)"));
            }
            if self.mode == 3 {
                let mut trace = checkbox(d.trace).label("Trace mode: measured advances");
                if !self.busy() {
                    trace = trace.on_toggle(Message::Trace);
                }
                advanced = advanced.push(focus::wrap(
                    trace,
                    "trace",
                    if !self.busy() {
                        focus::activate(Message::Trace(!d.trace))
                    } else {
                        vec![]
                    },
                ));
                if d.trace {
                    advanced =
                        advanced.push(self.field("advances", "Measured extra RNG calls (0–1000)"));
                }
            }
            let height = if self.mode == 3 && d.trace {
                220.0
            } else if self.mode == 0 || self.mode == 1 || self.mode == 3 {
                150.0
            } else {
                85.0
            };
            form = form.push(container(advanced).height(height * amount).clip(true));
        }

        form=form.push(text("Prepared-world evidence varies by mode. Survival construction and rates remain unverified.").size(12).color(CAUTION));
        form.into()
    }
    fn results(&self) -> Element<'_, Message> {
        let d = &self.drafts[self.mode];
        let mut content = column![text("Candidate").size(18)].spacing(16);
        if let Some(c) = &d.result {
            content = content.push(
                text(if d.dirty {
                    "Settings changed — search again to export"
                } else {
                    "Modeled candidate"
                })
                .size(21),
            );
            for (index, coordinate) in c.coordinates.iter().enumerate() {
                let xyz = coordinate.xyz.join(", ");
                content = content.push(
                    column![
                        text(&coordinate.label).size(12).color(MUTED),
                        row![
                            text(format!(
                                "X {}    Y {}    Z {}",
                                coordinate.xyz[0], coordinate.xyz[1], coordinate.xyz[2]
                            ))
                            .font(iced::Font::MONOSPACE)
                            .size(14),
                            self.action(10 + index, "Copy", Message::Copy(xyz), true, false)
                        ]
                        .spacing(12)
                    ]
                    .spacing(5),
                );
            }
            content = content.push(text("Build requirements").size(16));
            if c.requirements.is_empty() {
                content=content.push(text("Review the complete plan for clearance, startup and collection requirements.").size(13));
            }
            for requirement in &c.requirements {
                content = content.push(text(requirement).size(13));
            }
            content=content.push(text("Terrain scan covers base generation, not all population features or chunk history. A calculated candidate is not gameplay proof.").color(CAUTION).size(12));

            content = content.push(self.action(
                6,
                if d.plan_open {
                    "▾ Complete plan"
                } else {
                    "▸ Complete plan"
                },
                Message::Plan,
                true,
                false,
            ));
            if d.plan_open {
                content = content.push(text(&c.plan).size(13).font(iced::Font::MONOSPACE));
            }
        } else {
            content = content
                .push(text("No candidate yet").size(22))
                .push(text("Enter a world creation seed, then find a candidate.").color(MUTED));
        }
        let t = sample(&self.result_reveal);
        container(content)
            .padding(24)
            .width(Fill)
            .style(move |_| container::Style {
                background: Some(blend(BG, SURFACE, t).into()),
                border: iced::Border {
                    color: blend(SURFACE, FOCUS, 0.2),
                    width: 1.0,
                    radius: 6.0.into(),
                },
                ..Default::default()
            })
            .into()
    }
    fn view(&self) -> Element<'_, Message> {
        widget::responsive(|size| self.layout(size)).into()
    }
    fn layout(&self, size: iced::Size) -> Element<'_, Message> {
        let compact = size.height < 600.0;
        let inset = if compact { 12 } else { 24 };
        let mut tabs = row![].spacing(8);
        for (i, mode) in MODES.iter().enumerate() {
            let t = sample(&self.tabs[i]);
            let h = sample(&self.hover[i]);
            let b = button(text(*mode).size(15))
                .padding([10, 12])
                .on_press_maybe((!self.busy()).then_some(Message::Mode(i)))
                .style(move |_, status| button::Style {
                    background: Some(blend(SURFACE, PURPLE, (t + 0.12 * h).min(1.0)).into()),
                    text_color: INK,
                    border: iced::Border {
                        color: if t > 0.5 || status == button::Status::Hovered {
                            FOCUS
                        } else {
                            SURFACE
                        },
                        width: if t > 0.5 { 2.0 } else { 1.0 },
                        radius: 4.0.into(),
                    },
                    ..Default::default()
                });
            let mut keys = if !self.busy() {
                focus::activate(Message::Mode(i))
            } else {
                vec![]
            };
            if !self.busy() {
                keys.push((
                    iced::keyboard::Key::Named(iced::keyboard::key::Named::ArrowRight),
                    Message::Mode((i + 1) % 4),
                ));
                keys.push((
                    iced::keyboard::Key::Named(iced::keyboard::key::Named::ArrowLeft),
                    Message::Mode((i + 3) % 4),
                ));
            }
            tabs = tabs.push(focus::wrap(
                mouse_area(b)
                    .on_enter(Message::Hover(i, true))
                    .on_exit(Message::Hover(i, false)),
                format!("tab-{i}"),
                keys,
            ));
        }
        let header = container(
            column![
                row![
                    text("World RNG Finder").size(23),
                    Space::new().width(Fill),
                    text("Java 1.12.2").size(13).color(MUTED)
                ],
                tabs
            ]
            .spacing(if compact { 8 } else { 18 }),
        )
        .padding([12, inset])
        .style(|_| container::Style {
            background: Some(SURFACE.into()),
            ..Default::default()
        });
        let shared: Element<_> = if size.width < 700.0 {
            column![
                self.field("seed", "World creation seed"),
                row![
                    self.field("view", "View distance"),
                    self.field("x", "Block X"),
                    self.field("z", "Block Z")
                ]
                .spacing(12)
            ]
            .spacing(12)
            .into()
        } else {
            row![
                container(self.field("seed", "World creation seed")).width(Length::FillPortion(3)),
                self.field("view", "View distance (chunks)"),
                self.field("x", "Near block X"),
                self.field("z", "Near block Z")
            ]
            .spacing(16)
            .into()
        };
        let panels = widget::responsive(|size| {
            if size.width < 940.0 {
                scrollable(column![self.settings(), self.results()].spacing(24)).into()
            } else {
                row![
                    container(scrollable(self.settings())).width(Length::FillPortion(2)),
                    container(scrollable(self.results())).width(Length::FillPortion(3))
                ]
                .spacing(24)
                .into()
            }
        });
        let mut body = column![text("World & server").size(17), shared].spacing(14);
        if let Some(error) = &self.error {
            body = body.push(
                container(text(error).color(CAUTION).size(14))
                    .padding(12)
                    .style(container::rounded_box),
            );
        }
        let body: Element<_> = if compact {
            scrollable(body.push(self.settings()).push(self.results()).spacing(20))
                .height(Fill)
                .into()
        } else {
            body.push(panels).into()
        };
        let d = &self.drafts[self.mode];
        let ready = d.result.is_some() && !d.dirty && !self.busy();
        let search = if self.worker.is_some() {
            self.action(
                5,
                if self.cancelling.is_some() {
                    "Cancelling…"
                } else {
                    "Cancel"
                },
                Message::Cancel,
                self.cancelling.is_none(),
                false,
            )
        } else {
            self.action(
                5,
                if compact { "Find" } else { "Find candidate" },
                Message::Search(false),
                !self.busy(),
                true,
            )
        };
        let toolbar = row![
            search,
            Space::new().width(Fill),
            self.action(
                8,
                if compact { "Next" } else { "Next location" },
                Message::Search(true),
                ready,
                false
            ),
            self.action(9, "Export…", Message::Browse(true), ready, true)
        ]
        .spacing(12);

        let status = if self.worker.is_some() {
            format!("{}   •   {}s", self.stage, self.started.elapsed().as_secs())
        } else {
            self.stage.clone()
        };
        let status = if compact && status.chars().count() > 65 {
            format!("{}…", status.chars().take(64).collect::<String>())
        } else {
            status
        };
        let status_text = text(status).size(12).color(MUTED);
        let controls = row![
            Space::new().width(Fill),
            focus::wrap(
                checkbox(self.reduced)
                    .label("Reduced motion")
                    .on_toggle(Message::Reduced),
                "motion",
                focus::activate(Message::Reduced(!self.reduced))
            ),
            focus::wrap(
                pick_list([1.0, 1.5, 2.0], Some(self.scale), Message::Scale),
                "scale",
                vec![
                    (
                        iced::keyboard::Key::Named(iced::keyboard::key::Named::ArrowRight),
                        Message::Scale(if self.scale < 1.5 { 1.5 } else { 2.0 })
                    ),
                    (
                        iced::keyboard::Key::Named(iced::keyboard::key::Named::ArrowLeft),
                        Message::Scale(if self.scale > 1.5 { 1.5 } else { 1.0 })
                    )
                ]
            )
        ]
        .spacing(12)
        .align_y(iced::Alignment::Center);
        let footer: Element<_> = if compact {
            column![status_text, controls].spacing(6).into()
        } else {
            row![container(status_text).width(Fill), controls]
                .spacing(14)
                .align_y(iced::Alignment::Center)
                .into()
        };
        column![
            header,
            container(body).padding([12, inset]).height(Fill),
            container(toolbar).padding([0, inset]),
            container(footer).padding([8, inset])
        ]
        .into()
    }
}

fn main() -> iced::Result {
    iced::application(App::new, App::update, App::view)
        .title("World RNG Finder — Rust desktop")
        .theme(|_: &App| {
            Theme::custom(
                "Threadstone purple",
                iced::theme::Palette {
                    background: BG,
                    text: INK,
                    primary: PURPLE,
                    success: FOCUS,
                    danger: CAUTION,
                    warning: CAUTION,
                },
            )
        })
        .subscription(App::subscription)
        .scale_factor(|a: &App| a.scale as f32)
        .default_font(iced::Font::with_name("Noto Sans"))
        .window_size((1120.0, 820.0))
        .window(iced::window::Settings {
            size: iced::Size::new(1120.0, 820.0),
            min_size: Some(iced::Size::new(760.0, 600.0)),
            ..Default::default()
        })
        .run()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn shared_edits_invalidate_all_modes_and_preserve_previous_candidate() {
        let mut app = App::new();
        let _ = app.update(Message::Input("seed", "12345".into()));
        assert!(app.drafts.iter().all(|d| d.dirty));
        app.drafts[0].result = Some(Candidate {
            plan: "previous".into(),
            coordinates: vec![],
            requirements: vec![],
            region: vec!["-1".into(), "2".into()],
            index: 4,
            directory: PathBuf::new(),
        });
        app.drafts[0].dirty = false;
        assert_eq!(app.request(true)["values"]["skip"], "5");
        assert_eq!(
            app.request(true)["values"]["exclude_region"],
            json!(["-1", "2"])
        );
        let _ = app.update(Message::Input("bound", "80".into()));
        assert!(app.drafts[0].dirty);
        assert_eq!(app.drafts[0].result.as_ref().unwrap().plan, "previous");
        assert_eq!(app.request(false)["values"]["skip"], "0");
    }
    #[test]
    fn failed_worker_retains_previous_result() {
        let mut app = App::new();
        app.drafts[0].result = Some(Candidate {
            plan: "previous".into(),
            coordinates: vec![],
            requirements: vec![],
            region: vec![],
            index: 1,
            directory: PathBuf::new(),
        });
        app.start(json!({"action":"invalid"}));
        for _ in 0..200 {
            let _ = app.update(Message::Tick);
            if app.worker.is_none() {
                break;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        assert!(app.worker.is_none());
        assert!(app
            .error
            .as_ref()
            .unwrap()
            .contains("Unknown desktop action"));
        assert_eq!(app.drafts[0].result.as_ref().unwrap().plan, "previous");
        assert!(!app.drafts[0].dirty);
    }
    #[test]
    fn motion_reduction_finishes_animations() {
        let mut app = App::new();
        let _ = app.update(Message::Hover(5, true));
        let _ = app.update(Message::Reduced(true));
        assert!(!app.hover[5].is_animating(Instant::now()));
        assert_eq!(sample(&app.hover[5]), 1.0);
        let _ = app.update(Message::Mode(3));
        assert_eq!(sample(&app.tabs[3]), 1.0);
        assert!(!app.tabs[3].is_animating(Instant::now()));
    }
    #[cfg(unix)]
    #[test]
    fn worker_cancellation_stops_descendants() {
        use std::{fs, thread};
        let directory =
            std::env::temp_dir().join(format!("rng-cancel-test-{}", std::process::id()));
        fs::create_dir(&directory).unwrap();
        fs::write(directory.join("desktop_worker.py"),"import subprocess,time,pathlib\np=subprocess.Popen(['sleep','60'])\npathlib.Path('child.pid').write_text(str(p.pid))\ntime.sleep(60)\n").unwrap();
        let mut worker = Worker::start(&directory, json!({})).unwrap();
        for _ in 0..100 {
            if directory.join("child.pid").exists() {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        let pid: i32 = fs::read_to_string(directory.join("child.pid"))
            .unwrap()
            .parse()
            .unwrap();
        worker.cancel();
        for _ in 0..100 {
            if worker.finished() {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        assert!(worker.finished());
        drop(worker);
        // A terminated child may briefly remain a zombie until the container init reaps it.
        let state = fs::read_to_string(format!("/proc/{pid}/stat")).unwrap_or_default();
        assert!(
            state.is_empty() || state.split_whitespace().nth(2) == Some("Z"),
            "child still running: {state}"
        );
        fs::remove_dir_all(directory).unwrap();
    }
}
