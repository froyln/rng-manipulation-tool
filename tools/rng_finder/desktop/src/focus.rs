//! Keyboard focus for Iced controls that do not yet expose native focus.
use crate::{Message, FOCUS};
use iced::{
    advanced::{
        self, layout, mouse, renderer,
        widget::{self, tree, Operation, Tree},
        Clipboard, Layout, Shell, Widget,
    },
    keyboard::{self, key::Named, Key},
    Element, Event, Length, Rectangle, Size, Vector,
};

#[derive(Default)]
struct State {
    focused: bool,
}
impl widget::operation::Focusable for State {
    fn is_focused(&self) -> bool {
        self.focused
    }
    fn focus(&mut self) {
        self.focused = true;
    }
    fn unfocus(&mut self) {
        self.focused = false;
    }
}
struct Focus<'a> {
    content: Element<'a, Message>,
    id: widget::Id,
    keys: Vec<(Key, Message)>,
}
pub fn wrap<'a>(
    content: impl Into<Element<'a, Message>>,
    id: impl Into<widget::Id>,
    keys: Vec<(Key, Message)>,
) -> Element<'a, Message> {
    Element::new(Focus {
        content: content.into(),
        id: id.into(),
        keys,
    })
}
pub fn activate(message: Message) -> Vec<(Key, Message)> {
    vec![
        (Key::Named(Named::Enter), message.clone()),
        (Key::Named(Named::Space), message),
    ]
}

/// Reveal keyboard focus inside its owning scroll area. Iced's focus operations
/// change focus state but do not adjust scroll offsets.
pub fn reveal() -> iced::Task<Message> {
    advanced::widget::operate(Reveal::default())
}

#[derive(Default)]
struct Reveal {
    pending: Option<(widget::Id, Rectangle, Vector)>,
    ancestors: Vec<(widget::Id, Rectangle, Vector)>,
    adjustment: Option<(widget::Id, f32)>,
}

#[cfg(test)]
mod reveal_tests {
    use super::*;

    fn area() -> (widget::Id, Rectangle, Vector) {
        (
            widget::Id::new("settings"),
            Rectangle {
                x: 0.0,
                y: 100.0,
                width: 300.0,
                height: 200.0,
            },
            Vector::new(0.0, 50.0),
        )
    }
    #[test]
    fn focus_below_and_above_viewport_scrolls_by_hidden_distance() {
        let mut reveal = Reveal::default();
        reveal.ancestors.push(area());
        let mut state = State { focused: true };
        let mut bounds = Rectangle {
            x: 0.0,
            y: 400.0,
            width: 100.0,
            height: 40.0,
        };
        reveal.focusable(None, bounds, &mut state);
        assert_eq!(reveal.adjustment.as_ref().unwrap().1, 90.0);
        bounds.y = 120.0;
        reveal.focusable(None, bounds, &mut state);
        assert_eq!(reveal.adjustment.as_ref().unwrap().1, -30.0);
    }
    #[test]
    fn visible_focus_and_controls_outside_scroll_area_do_not_scroll() {
        let mut reveal = Reveal::default();
        let mut state = State { focused: true };
        let bounds = Rectangle {
            x: 0.0,
            y: 200.0,
            width: 100.0,
            height: 40.0,
        };
        reveal.focusable(None, bounds, &mut state);
        assert!(reveal.adjustment.is_none());
        reveal.ancestors.push(area());
        reveal.focusable(None, bounds, &mut state);
        assert!(reveal.adjustment.is_none());
        state.focused = false;
        reveal.focusable(None, Rectangle { y: 500.0, ..bounds }, &mut state);
        assert!(reveal.adjustment.is_none());
    }
}
impl Operation<Message> for Reveal {
    fn scrollable(
        &mut self,
        id: Option<&widget::Id>,
        bounds: Rectangle,
        _content: Rectangle,
        translation: Vector,
        _state: &mut dyn widget::operation::Scrollable,
    ) {
        self.pending = id.cloned().map(|id| (id, bounds, translation));
    }
    fn traverse(&mut self, operate: &mut dyn FnMut(&mut dyn Operation<Message>)) {
        let entering = self.pending.take();
        let pushed = entering.is_some();
        if let Some(area) = entering {
            self.ancestors.push(area);
        }
        operate(self);
        if pushed {
            self.ancestors.pop();
        }
    }
    fn focusable(
        &mut self,
        _id: Option<&widget::Id>,
        bounds: Rectangle,
        state: &mut dyn widget::operation::Focusable,
    ) {
        if state.is_focused() {
            if let Some((id, viewport, translation)) = self.ancestors.last() {
                let top = bounds.y - translation.y;
                let bottom = top + bounds.height;
                let delta = if top < viewport.y {
                    top - viewport.y
                } else if bottom > viewport.y + viewport.height {
                    bottom - (viewport.y + viewport.height)
                } else {
                    0.0
                };
                if delta != 0.0 {
                    self.adjustment = Some((id.clone(), delta));
                }
            }
        }
    }
    fn finish(&self) -> widget::operation::Outcome<Message> {
        if let Some((id, y)) = &self.adjustment {
            widget::operation::Outcome::Chain(Box::new(widget::operation::scrollable::scroll_by(
                id.clone(),
                widget::operation::scrollable::AbsoluteOffset { x: 0.0, y: *y },
            )))
        } else {
            widget::operation::Outcome::None
        }
    }
}
impl Widget<Message, iced::Theme, iced::Renderer> for Focus<'_> {
    fn tag(&self) -> tree::Tag {
        tree::Tag::of::<State>()
    }
    fn state(&self) -> tree::State {
        tree::State::new(State::default())
    }
    fn children(&self) -> Vec<Tree> {
        vec![Tree::new(&self.content)]
    }
    fn diff(&self, tree: &mut Tree) {
        tree.diff_children(std::slice::from_ref(&self.content));
    }
    fn size(&self) -> Size<Length> {
        self.content.as_widget().size()
    }
    fn layout(
        &mut self,
        tree: &mut Tree,
        renderer: &iced::Renderer,
        limits: &layout::Limits,
    ) -> layout::Node {
        self.content
            .as_widget_mut()
            .layout(&mut tree.children[0], renderer, limits)
    }
    fn operate(
        &mut self,
        tree: &mut Tree,
        layout: Layout<'_>,
        renderer: &iced::Renderer,
        operation: &mut dyn Operation,
    ) {
        if !self.keys.is_empty() {
            operation.focusable(
                Some(&self.id),
                layout.bounds(),
                tree.state.downcast_mut::<State>(),
            );
        }
        self.content
            .as_widget_mut()
            .operate(&mut tree.children[0], layout, renderer, operation);
    }
    fn update(
        &mut self,
        tree: &mut Tree,
        event: &Event,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        renderer: &iced::Renderer,
        clipboard: &mut dyn Clipboard,
        shell: &mut Shell<'_, Message>,
        viewport: &Rectangle,
    ) {
        let state = tree.state.downcast_mut::<State>();
        if matches!(
            event,
            Event::Mouse(mouse::Event::ButtonPressed(mouse::Button::Left))
        ) {
            state.focused = cursor.is_over(layout.bounds()) && !self.keys.is_empty();
        }
        if state.focused {
            if let Event::Keyboard(keyboard::Event::KeyPressed { key, modifiers, .. }) = event {
                if let Some((_, message)) = self
                    .keys
                    .iter()
                    .find(|(k, _)| k == key && !modifiers.control() && !modifiers.alt())
                {
                    shell.publish(message.clone());
                    shell.capture_event();
                    return;
                }
            }
        }
        self.content.as_widget_mut().update(
            &mut tree.children[0],
            event,
            layout,
            cursor,
            renderer,
            clipboard,
            shell,
            viewport,
        );
    }
    fn draw(
        &self,
        tree: &Tree,
        renderer: &mut iced::Renderer,
        theme: &iced::Theme,
        style: &renderer::Style,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
    ) {
        self.content.as_widget().draw(
            &tree.children[0],
            renderer,
            theme,
            style,
            layout,
            cursor,
            viewport,
        );
        if tree.state.downcast_ref::<State>().focused && !self.keys.is_empty() {
            use advanced::Renderer;
            renderer.fill_quad(
                renderer::Quad {
                    bounds: layout.bounds(),
                    border: iced::Border {
                        color: FOCUS,
                        width: 2.0,
                        radius: 4.0.into(),
                    },
                    ..Default::default()
                },
                iced::Color::TRANSPARENT,
            );
        }
    }
    fn mouse_interaction(
        &self,
        tree: &Tree,
        layout: Layout<'_>,
        cursor: mouse::Cursor,
        viewport: &Rectangle,
        renderer: &iced::Renderer,
    ) -> mouse::Interaction {
        self.content.as_widget().mouse_interaction(
            &tree.children[0],
            layout,
            cursor,
            viewport,
            renderer,
        )
    }
    fn overlay<'b>(
        &'b mut self,
        tree: &'b mut Tree,
        layout: Layout<'b>,
        renderer: &iced::Renderer,
        viewport: &Rectangle,
        translation: Vector,
    ) -> Option<advanced::overlay::Element<'b, Message, iced::Theme, iced::Renderer>> {
        self.content.as_widget_mut().overlay(
            &mut tree.children[0],
            layout,
            renderer,
            viewport,
            translation,
        )
    }
}
