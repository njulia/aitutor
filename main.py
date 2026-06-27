import argparse
import logging

from src.ai_tutor import process_homework_with_review, run_gui, run_tui


# 1. Configure logging settings
logging.basicConfig(
    level=logging.DEBUG,  # Set the lowest level to capture
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("aitutor.log"),  # Save logs to a file
        logging.StreamHandler()          # Print logs to the console
    ]
)
# 2. Create a logger
logger = logging.getLogger(__name__)

# #   print("Unknown argument. Available options:")
#             print("  --tui     : Terminal interactive mode")
#             print(f"  --prompt  : Generate/import {NUM_DAYS}-day homework with review from natural language prompt")
#             print("  (no arg)  : Web GUI mode (default)")
#             print("\nExample: python hybrid_english_tutor_langgraph.py --prompt 'I need Math, English, and Science homework for this week'")
def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Run AI Tutor")
    parser.add_argument(
    "--tui", action="store_true", required=False, help="Run in terminal interactive mode"
    )
    parser.add_argument(
    "--prompt", type=str, required=False, help="Input prompt for homework generation/import with review"
    )
    args = parser.parse_args()

    try:
        if args.tui:
            run_tui()
        elif args.prompt:
            # 从命令行提示词生成/导入作业并点评
            user_input = args.prompt
            student_id = "student1"
            filepath = process_homework_with_review(user_input, student_id)
            logger.info(f"\nDone! Homework with review saved to: {filepath}")
        else:
            run_gui()
    except KeyboardInterrupt:
        logger.warning("操作被中断。")
    finally:
        logger.warning("程序退出。")


if __name__ == "__main__":
    main()


