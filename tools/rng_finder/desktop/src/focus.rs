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
