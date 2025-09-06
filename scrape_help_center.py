import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import time
import re
from typing import List, Dict, Optional
from datetime import datetime

def extract_faq_sections(page) -> List[Dict]:
    """Extract FAQ sections by finding question containers with '?' in child div and clicking to reveal answers."""
    faq_sections = []

    try:
        print("Finding all FAQ question containers...")

        # Select all divs with tabindex=0 and css-g5y9jx class (accordion headers)
        question_containers = page.query_selector_all('div[tabindex="0"].css-g5y9jx')
        print(f"Found {len(question_containers)} potential question containers")

        for i, container in enumerate(question_containers, 1):
            try:
                # Check for child div with text containing '?'
                question_el = None
                for child in container.query_selector_all('div[dir="auto"]'):
                    txt = child.inner_text().strip()
                    if "?" in txt:
                        question_el = child
                        break

                if not question_el:
                    continue  # skip if no '?' found

                question_text = question_el.inner_text().strip()
                if not question_text or len(question_text) < 5:
                    continue

                print(f"\nProcessing question {i}: {question_text[:100]}...")

                # Snapshot body text before clicking
                before_text = set(
                    t.strip() for t in page.inner_text('body').split('\n') if t.strip()
                )

                # Click container to expand
                try:
                    container.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    container.click()
                    time.sleep(1.5)  # wait for animation/answer to load
                except Exception as e:
                    print(f"Could not click container: {str(e)}")
                    continue

                # Snapshot after click
                after_text = set(
                    t.strip() for t in page.inner_text('body').split('\n') if t.strip()
                )

                # Find new text
                new_texts = after_text - before_text

                if new_texts:
                    # Filter out the question text itself
                    answer = " ".join(
                        t for t in new_texts
                        if t != question_text and not t.startswith(question_text[:20])
                    )
                    if answer and len(answer) > 10:
                        faq_sections.append({
                            "question": question_text,
                            "answer": answer
                        })
                        print(f"Found answer: {answer[:60]}...")

                # Collapse back
                try:
                    container.click()
                    time.sleep(0.3)
                except:
                    pass

            except Exception as e:
                print(f"Error processing question {i}: {str(e)}")
                continue

    except Exception as e:
        print(f"Error in extract_faq_sections: {str(e)}")

    return faq_sections



def scrape_help_center():
    """Main function to scrape the JioPay help center."""
    help_center_url = "https://jiopay.com/business/help-center"
    knowledge_base = []

    with sync_playwright() as p:
        # Launch browser in non-headless mode for debugging
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 1000},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='Asia/Kolkata',
            permissions=['geolocation']
        )

        # Add cookies and local storage to make it appear more like a real user
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.localStorage.setItem('user_consent', 'true');
        """)

        page = context.new_page()

        try:
            print(f"Accessing {help_center_url}...")
            page.goto(help_center_url, timeout=120000, wait_until='networkidle')

            # Wait for the main content to load
            print("Waiting for page content to load...")
            try:
                # Wait for either the FAQ container or a reasonable timeout
                page.wait_for_selector('.css-14lw9ot.r-1m36w87', state='visible', timeout=30000)
            except PlaywrightTimeoutError:
                print("Warning: FAQ sections not found, but continuing with extraction...")

            # Scroll to load any lazy-loaded content
            print("Scrolling to load content...")
            for _ in range(3):  # Scroll multiple times to load all content
                page.evaluate('window.scrollBy(0, window.innerHeight)')
                time.sleep(1)

            # Extract FAQ sections
            print("\nStarting FAQ extraction...")
            faq_items = extract_faq_sections(page)

            # Save the extracted data
            knowledge_base.append({
                'source': 'JioPay Help Center',
                'url': help_center_url,
                'faqs': faq_items,
                'extracted_at': datetime.now().isoformat(),
                'metadata': {
                    'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                    'viewport': '1280x1000',
                    'total_questions': len(faq_items)
                }
            })

            # Save to JSON file
            output_file = 'jiopay_help_center.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

            print(f"\nScraping completed. Found {len(faq_items)} questions with answers.")
            print(f"Data saved to {output_file}")

            return knowledge_base

        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            # Save partial results if any
            if knowledge_base:
                output_file = 'jiopay_help_center_partial.json'
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
                print(f"\nPartial results saved to {output_file}")
            raise

        finally:
            # Close the browser
            print("\nClosing browser...")
            browser.close()


if __name__ == "__main__":
    scrape_help_center()