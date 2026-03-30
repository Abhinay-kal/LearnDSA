import java.util.Scanner;

class Solution {
    public int firstUniqChar(String s) {
        // Step 1: Create a frequency array for 26 lowercase English letters
        // This is a fixed-size hash table (Space: O(1))
        int[] freq = new int[26];

        // Step 2: Fill the frequency array (First Pass)
        for (int i = 0; i < s.length(); i++) {
            freq[s.charAt(i) - 'a']++;
        }

        // Step 3: Find the first character with a count of 1 (Second Pass)
        for (int i = 0; i < s.length(); i++) {
            if (freq[s.charAt(i) - 'a'] == 1) {
                return i;
            }
        }

        // Step 4: If no unique character is found
        return -1;
    }

    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        if (sc.hasNextLine()) {
            String s = sc.nextLine();
            Solution so = new Solution();
            int result = so.firstUniqChar(s);
            System.out.println(result);
        }
        sc.close();
    }
}