from unittest.mock import Mock, patch


from src.streamwatch.menu_handler import MenuHandler


class TestMenuHandler:
    def test_init(self):
        """Test MenuHandler initialization."""
        mh = MenuHandler(command_invoker=Mock())
        assert mh.last_message == ""

    def test_clear_message(self):
        """Test clearing the last message."""
        mh = MenuHandler()
        mh.last_message = "test message"
        mh.clear_message()
        assert mh.last_message == ""

    @patch("src.streamwatch.menu_handler.ui")
    def test_display_main_menu(self, mock_ui):
        """Test displaying the main menu."""
        mh = MenuHandler()
        mh.display_main_menu(5)
        mock_ui.display_main_menu.assert_called_once_with(5)

    def test_handle_user_input_with_mock(self):
        """Test handling user input."""
        mh = MenuHandler()
        with patch(
            "src.streamwatch.menu_handler.ui.prompt_main_menu_action"
        ) as mock_input:
            mock_input.return_value = "q"
            result = mh.handle_user_input()
            assert result == "q"
