from parser import extract_claims
transcript = """
President Trump writing on his social media platform early Sunday that the US Navy will begin the process of blockading all ships trying to enter or leave the Strait of Hormuz.
"""
print(extract_claims(transcript))
